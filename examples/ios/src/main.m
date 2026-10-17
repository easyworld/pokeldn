// The iOS app: the embedded Python serves gui/main.py as Flet's web app on 127.0.0.1, a WKWebView
// shows it, and the radio board's Bluetooth link is a byte stream on 127.0.0.1:47811 that
// pokeldn.ldn.esp32 opens as socket:// (examples/ios/README.md).
#import <UIKit/UIKit.h>
#import <WebKit/WebKit.h>
#import <CoreBluetooth/CoreBluetooth.h>
#import <UniformTypeIdentifiers/UniformTypeIdentifiers.h>
#import <Python/Python.h>
#include <arpa/inet.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <sys/socket.h>
#include <unistd.h>

static const int GUI_PORT = 8550;
static const int RADIO_PORT = 47811;
static const int CONTROL_PORT = 47812;   // pokeldn/app/ios.py: one request line, one reply

#pragma mark - The radio over Bluetooth

// docs/hardware_esp32.md, Bluetooth: the service and its RX (host writes) and TX (board notifies).
static NSString *const SERVICE = @"7a1e0101-5d2c-4c3e-9f4b-504f4b454c44";
static NSString *const RX = @"7a1e0102-5d2c-4c3e-9f4b-504f4b454c44";
static NSString *const TX = @"7a1e0103-5d2c-4c3e-9f4b-504f4b454c44";

@interface RadioBridge : NSObject <CBCentralManagerDelegate, CBPeripheralDelegate>
@property (nonatomic, strong) CBCentralManager *central;
@property (nonatomic, strong) CBPeripheral *board;
@property (nonatomic, strong) CBCharacteristic *rx;
@property (nonatomic, strong) NSMutableData *pending;   // socket bytes the board has not taken yet
@property (atomic) int client;                          // the one Python connection, or -1
@property (nonatomic, strong) dispatch_queue_t queue;
@end

@implementation RadioBridge

// pokeldn/app/ios.py reads it: the board is listed as a port only while it is ready.
- (void)setState:(NSString *)state
{
    NSString *documents = NSSearchPathForDirectoriesInDomains(NSDocumentDirectory, NSUserDomainMask, YES)[0];
    [state writeToFile:[documents stringByAppendingPathComponent:@".radio"] atomically:YES
              encoding:NSUTF8StringEncoding error:nil];
}

- (instancetype)init
{
    if ((self = [super init])) {
        _client = -1;
        _pending = [NSMutableData data];
        _queue = dispatch_queue_create("pokeldn.radio", DISPATCH_QUEUE_SERIAL);
        [self setState:@"off"];
        _central = [[CBCentralManager alloc] initWithDelegate:self queue:_queue];
        [NSThread detachNewThreadSelector:@selector(listen) toTarget:self withObject:nil];
    }
    return self;
}

- (void)centralManagerDidUpdateState:(CBCentralManager *)central
{
    if (central.state == CBManagerStatePoweredOn) [self scan];
    else [self setState:@"off"];
}

- (void)scan
{
    [self setState:@"scanning"];
    // The board advertises its name only (firmware ble.c); the service UUID would not fit beside it.
    [self.central scanForPeripheralsWithServices:nil options:nil];
}

- (void)centralManager:(CBCentralManager *)central didDiscoverPeripheral:(CBPeripheral *)peripheral
     advertisementData:(NSDictionary *)data RSSI:(NSNumber *)rssi
{
    NSString *name = data[CBAdvertisementDataLocalNameKey] ?: peripheral.name;
    if (![name isEqualToString:@"POKELDN-RADIO"]) return;
    [central stopScan];
    self.board = peripheral;
    peripheral.delegate = self;
    [central connectPeripheral:peripheral options:nil];
}

- (void)centralManager:(CBCentralManager *)central didConnectPeripheral:(CBPeripheral *)peripheral
{
    [peripheral discoverServices:@[[CBUUID UUIDWithString:SERVICE]]];
}

- (void)centralManager:(CBCentralManager *)central didDisconnectPeripheral:(CBPeripheral *)peripheral error:(NSError *)error
{
    self.rx = nil;
    self.board = nil;
    [self dropClient];
    [self scan];
}

- (void)centralManager:(CBCentralManager *)central didFailToConnectPeripheral:(CBPeripheral *)peripheral error:(NSError *)error
{
    [self scan];
}

- (void)peripheral:(CBPeripheral *)peripheral didDiscoverServices:(NSError *)error
{
    for (CBService *service in peripheral.services)
        [peripheral discoverCharacteristics:@[[CBUUID UUIDWithString:RX], [CBUUID UUIDWithString:TX]] forService:service];
}

- (void)peripheral:(CBPeripheral *)peripheral didDiscoverCharacteristicsForService:(CBService *)service error:(NSError *)error
{
    for (CBCharacteristic *c in service.characteristics) {
        if ([c.UUID isEqual:[CBUUID UUIDWithString:RX]]) self.rx = c;
        if ([c.UUID isEqual:[CBUUID UUIDWithString:TX]]) [peripheral setNotifyValue:YES forCharacteristic:c];
    }
}

- (void)peripheral:(CBPeripheral *)peripheral didUpdateNotificationStateForCharacteristic:(CBCharacteristic *)c error:(NSError *)error
{
    if (!error && c.isNotifying) [self setState:@"ready"];
}

- (void)peripheral:(CBPeripheral *)peripheral didUpdateValueForCharacteristic:(CBCharacteristic *)c error:(NSError *)error
{
    const int fd = self.client;
    NSData *value = c.value;
    if (fd < 0 || !value.length) return;
    const uint8_t *p = value.bytes;
    size_t left = value.length;
    while (left) {
        const ssize_t n = send(fd, p, left, 0);
        if (n <= 0) { [self dropClient]; return; }
        p += n;
        left -= n;
    }
}

// CoreBluetooth drops a write without response its queue cannot take (docs/hardware_pad.md).
- (void)drain
{
    if (!self.board || !self.rx) return;
    const NSUInteger piece = [self.board maximumWriteValueLengthForType:CBCharacteristicWriteWithoutResponse];
    while (self.pending.length && self.board.canSendWriteWithoutResponse) {
        const NSUInteger n = MIN(piece, self.pending.length);
        [self.board writeValue:[self.pending subdataWithRange:NSMakeRange(0, n)] forCharacteristic:self.rx
                          type:CBCharacteristicWriteWithoutResponse];
        [self.pending replaceBytesInRange:NSMakeRange(0, n) withBytes:NULL length:0];
    }
}

- (void)peripheralIsReadyToSendWriteWithoutResponse:(CBPeripheral *)peripheral
{
    [self drain];
}

- (void)dropClient
{
    const int fd = self.client;
    self.client = -1;
    if (fd >= 0) close(fd);
}

// One connection at a time: a run opens the board, as a desktop run opens its serial port.
- (void)listen
{
    const int server = socket(AF_INET, SOCK_STREAM, 0);
    const int on = 1;
    setsockopt(server, SOL_SOCKET, SO_REUSEADDR, &on, sizeof(on));
    struct sockaddr_in addr = {.sin_family = AF_INET, .sin_port = htons(RADIO_PORT),
                               .sin_addr.s_addr = htonl(INADDR_LOOPBACK)};
    if (bind(server, (struct sockaddr *)&addr, sizeof(addr)) || listen(server, 1)) {
        NSLog(@"pokeldn: radio socket unavailable");
        return;
    }
    for (;;) {
        const int fd = accept(server, NULL, NULL);
        if (fd < 0) continue;
        setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &on, sizeof(on));
        dispatch_sync(self.queue, ^{
            [self dropClient];
            [self.pending setLength:0];
            self.client = fd;
        });
        uint8_t chunk[4096];
        ssize_t n;
        while ((n = recv(fd, chunk, sizeof(chunk), 0)) > 0) {
            NSData *data = [NSData dataWithBytes:chunk length:n];
            dispatch_async(self.queue, ^{
                if (self.client != fd) return;
                [self.pending appendData:data];
                [self drain];
            });
        }
        dispatch_async(self.queue, ^{ if (self.client == fd) [self dropClient]; });
    }
}

@end

#pragma mark - Files

// "pick 0|1" answers the copied files' paths, one per line; "save PATH" exports a file and answers
// "ok" or nothing. The pickers copy: a picked file lands in the app's tmp/Inbox.
@interface FileBridge : NSObject <UIDocumentPickerDelegate>
@property (nonatomic, strong) NSArray<NSURL *> *picked;
@property (nonatomic, strong) dispatch_semaphore_t done;
@end

@implementation FileBridge

- (instancetype)init
{
    if ((self = [super init])) [NSThread detachNewThreadSelector:@selector(listen) toTarget:self withObject:nil];
    return self;
}

- (void)documentPicker:(UIDocumentPickerViewController *)controller didPickDocumentsAtURLs:(NSArray<NSURL *> *)urls
{
    self.picked = urls;
    dispatch_semaphore_signal(self.done);
}

- (void)documentPickerWasCancelled:(UIDocumentPickerViewController *)controller
{
    self.picked = @[];
    dispatch_semaphore_signal(self.done);
}

- (NSString *)answer:(NSString *)request
{
    self.picked = @[];
    self.done = dispatch_semaphore_create(0);
    dispatch_async(dispatch_get_main_queue(), ^{
        UIDocumentPickerViewController *picker;
        if ([request hasPrefix:@"save "]) {
            NSURL *file = [NSURL fileURLWithPath:[request substringFromIndex:5]];
            picker = [[UIDocumentPickerViewController alloc] initForExportingURLs:@[file] asCopy:YES];
        } else {
            picker = [[UIDocumentPickerViewController alloc] initForOpeningContentTypes:@[UTTypeItem] asCopy:YES];
            picker.allowsMultipleSelection = [request hasSuffix:@"1"];
        }
        picker.delegate = self;
        UIWindowScene *scene = (UIWindowScene *)UIApplication.sharedApplication.connectedScenes.anyObject;
        UIViewController *top = scene.windows.firstObject.rootViewController;
        while (top.presentedViewController) top = top.presentedViewController;
        [top presentViewController:picker animated:YES completion:nil];
    });
    dispatch_semaphore_wait(self.done, DISPATCH_TIME_FOREVER);
    if ([request hasPrefix:@"save "]) return self.picked.count ? @"ok" : @"";
    NSMutableArray *paths = [NSMutableArray array];
    for (NSURL *url in self.picked) [paths addObject:url.path];
    return [paths componentsJoinedByString:@"\n"];
}

- (void)listen
{
    const int server = socket(AF_INET, SOCK_STREAM, 0);
    const int on = 1;
    setsockopt(server, SOL_SOCKET, SO_REUSEADDR, &on, sizeof(on));
    struct sockaddr_in addr = {.sin_family = AF_INET, .sin_port = htons(CONTROL_PORT),
                               .sin_addr.s_addr = htonl(INADDR_LOOPBACK)};
    if (bind(server, (struct sockaddr *)&addr, sizeof(addr)) || listen(server, 4)) return;
    for (;;) {
        const int fd = accept(server, NULL, NULL);
        if (fd < 0) continue;
        NSMutableData *line = [NSMutableData data];
        uint8_t c;
        while (recv(fd, &c, 1, 0) == 1 && c != '\n') [line appendBytes:&c length:1];
        NSString *request = [[NSString alloc] initWithData:line encoding:NSUTF8StringEncoding] ?: @"";
        NSData *reply = [[[self answer:request] stringByAppendingString:@"\n"] dataUsingEncoding:NSUTF8StringEncoding];
        send(fd, reply.bytes, reply.length, 0);
        close(fd);
    }
}

@end

#pragma mark - Python

static void run_python(void)
{
    NSString *resources = [[NSBundle mainBundle] resourcePath];
    NSString *documents = NSSearchPathForDirectoriesInDomains(NSDocumentDirectory, NSUserDomainMask, YES)[0];
    setenv("POKELDN_IOS_DOCUMENTS", documents.UTF8String, 1);
    setenv("POKELDN_IOS_RADIO", [NSString stringWithFormat:@"socket://127.0.0.1:%d", RADIO_PORT].UTF8String, 1);
    if ([NSProcessInfo.processInfo.arguments containsObject:@"--selftest"]) setenv("POKELDN_IOS_SELFTEST", "1", 1);
    if ([NSProcessInfo.processInfo.arguments containsObject:@"--host-test"]) setenv("POKELDN_IOS_HOSTTEST", "1", 1);
    if ([NSProcessInfo.processInfo.arguments containsObject:@"--profile"]) setenv("POKELDN_IOS_PROFILE", "1", 1);
    if ([NSProcessInfo.processInfo.arguments containsObject:@"--clean"]) setenv("POKELDN_IOS_CLEAN", "1", 1);
    setenv("POKELDN_GUI_WEB", [NSString stringWithFormat:@"%d", GUI_PORT].UTF8String, 1);

    PyPreConfig preconfig;
    PyConfig config;
    PyPreConfig_InitIsolatedConfig(&preconfig);
    PyConfig_InitIsolatedConfig(&config);
    preconfig.utf8_mode = 1;
    config.buffered_stdio = 0;
    config.write_bytecode = 0;   // the signed bundle is read-only
    config.install_signal_handlers = 1;
    PyStatus status = Py_PreInitialize(&preconfig);
    if (PyStatus_Exception(status)) { NSLog(@"pokeldn: Python pre-init: %s", status.err_msg); return; }

    wchar_t *home = Py_DecodeLocale([resources stringByAppendingPathComponent:@"python"].UTF8String, NULL);
    PyConfig_SetString(&config, &config.home, home);
    PyMem_RawFree(home);
    config.module_search_paths_set = 1;
    NSArray *paths = @[@"python/lib/python3.13", @"python/lib/python3.13/lib-dynload", @"app", @"app_packages"];
    for (NSString *path in paths) {
        wchar_t *w = Py_DecodeLocale([resources stringByAppendingPathComponent:path].UTF8String, NULL);
        PyWideStringList_Append(&config.module_search_paths, w);
        PyMem_RawFree(w);
    }
    // CPython sends print() to the system log on iOS; the player's report needs a file (README).
    config.run_command = Py_DecodeLocale(
        "import os, sys, runpy, traceback\n"
        "sys.stdout = sys.stderr = open(os.environ['POKELDN_IOS_DOCUMENTS'] + '/pokeldn.log', 'w', buffering=1)\n"
        "try:\n    runpy.run_module('ios_gui', run_name='__main__')\n"
        "except BaseException:\n    traceback.print_exc()\n    raise\n", NULL);
    status = Py_InitializeFromConfig(&config);
    PyConfig_Clear(&config);
    if (PyStatus_Exception(status)) { NSLog(@"pokeldn: Python init: %s", status.err_msg); return; }
    const int code = Py_RunMain();
    NSLog(@"pokeldn: Python exited with %d", code);
}

#pragma mark - The app

@interface ViewController : UIViewController
@property (nonatomic, strong) WKWebView *web;
@end

@implementation ViewController

- (UIStatusBarStyle)preferredStatusBarStyle
{
    return UIStatusBarStyleLightContent;
}

- (void)viewDidLoad
{
    [super viewDidLoad];
    // gui/theme.py BG behind the status bar and the home indicator; the page stays inside the safe area.
    self.view.backgroundColor = [UIColor colorWithRed:0x0B / 255.0 green:0x0B / 255.0 blue:0x0D / 255.0 alpha:1];
    WKWebViewConfiguration *config = [WKWebViewConfiguration new];
    self.web = [[WKWebView alloc] initWithFrame:CGRectZero configuration:config];
    self.web.opaque = NO;
    self.web.backgroundColor = UIColor.clearColor;
    self.web.scrollView.contentInsetAdjustmentBehavior = UIScrollViewContentInsetAdjustmentNever;
    self.web.translatesAutoresizingMaskIntoConstraints = NO;
    [self.view addSubview:self.web];
    UILayoutGuide *safe = self.view.safeAreaLayoutGuide;
    [NSLayoutConstraint activateConstraints:@[
        [self.web.topAnchor constraintEqualToAnchor:safe.topAnchor],
        [self.web.bottomAnchor constraintEqualToAnchor:safe.bottomAnchor],
        [self.web.leadingAnchor constraintEqualToAnchor:safe.leadingAnchor],
        [self.web.trailingAnchor constraintEqualToAnchor:safe.trailingAnchor],
    ]];
    [self waitForServer];
}

// The server is up once the port answers; the first start unpacks nothing and takes a few seconds.
- (void)waitForServer
{
    NSURL *url = [NSURL URLWithString:[NSString stringWithFormat:@"http://127.0.0.1:%d/", GUI_PORT]];
    [[NSURLSession.sharedSession dataTaskWithURL:url completionHandler:^(NSData *d, NSURLResponse *r, NSError *e) {
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(e ? 0.3 * NSEC_PER_SEC : 0)), dispatch_get_main_queue(), ^{
            if (e) [self waitForServer];
            else [self.web loadRequest:[NSURLRequest requestWithURL:url]];
        });
    }] resume];
}

@end

@interface AppDelegate : UIResponder <UIApplicationDelegate>
@property (nonatomic, strong) RadioBridge *radio;
@property (nonatomic, strong) FileBridge *files;
@end

@implementation AppDelegate

- (BOOL)application:(UIApplication *)application didFinishLaunchingWithOptions:(NSDictionary *)options
{
    self.radio = [RadioBridge new];
    self.files = [FileBridge new];
    NSThread *python = [[NSThread alloc] initWithBlock:^{ run_python(); }];
    python.stackSize = 8 << 20;
    [python start];
    application.idleTimerDisabled = YES;   // a trade must not lose the screen mid-session
    return YES;
}

@end

// iOS 27 on a device stops an app with no scene lifecycle at launch (UIKit's
// NoSceneLifecycleAdoption trap); the simulator does not. Info.plist names this class.
@interface SceneDelegate : UIResponder <UIWindowSceneDelegate>
@property (nonatomic, strong) UIWindow *window;
@end

@implementation SceneDelegate

- (void)scene:(UIScene *)scene willConnectToSession:(UISceneSession *)session options:(UISceneConnectionOptions *)options
{
    self.window = [[UIWindow alloc] initWithWindowScene:(UIWindowScene *)scene];
    self.window.rootViewController = [ViewController new];
    [self.window makeKeyAndVisible];
}

@end

int main(int argc, char *argv[])
{
    @autoreleasepool {
        return UIApplicationMain(argc, argv, nil, NSStringFromClass([AppDelegate class]));
    }
}
