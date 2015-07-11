from __future__ import absolute_import, print_function
__author__ = 'cherie'

from libpebble2.communication.transports.websocket import MessageTargetPhone
from libpebble2.communication.transports.websocket.protocol import AppConfigCancelled, AppConfigResponse, AppConfigSetup
from libpebble2.communication.transports.websocket.protocol import WebSocketPhonesimAppConfig
from libpebble2.communication.transports.websocket.protocol import WebSocketPhonesimConfigResponse, WebSocketRelayQemu
from libpebble2.communication.transports.qemu.protocol import *
from libpebble2.communication.transports.qemu import MessageTargetQemu, QemuTransport
import os

from .base import PebbleCommand
from ..exceptions import ToolError
from pebble_tool.sdk.emulator import ManagedEmulatorTransport
from pebble_tool.util.browser import BrowserController


class EmuAccelCommand(PebbleCommand):
    command = 'emu-accel'

    def __call__(self, args):
        super(EmuAccelCommand, self).__call__(args)
        print("Running {}...".format(self.command))
        if args.motion == 'custom' and args.file is not None:
            samples = []
            with open(args.file) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        sample = []
                        for x in line.split(','):
                            sample.append(int(x))
                        samples.append(QemuAccelSample(x=sample[0], y=sample[1], z=sample[2]))
        elif args.motion != 'custom':
            samples = {
                'tilt-left': [QemuAccelSample(x=-500, y=0, z=-900),
                              QemuAccelSample(x=-900, y=0, z=-500),
                              QemuAccelSample(x=-1000, y=0, z=0)],
                'tilt-right': [QemuAccelSample(x=500, y=0, z=-900),
                               QemuAccelSample(x=900, y=0, z=-500),
                               QemuAccelSample(x=1000, y=0, z=0)],
                'tilt-forward': [QemuAccelSample(x=0, y=500, z=-900),
                                 QemuAccelSample(x=0, y=900, z=-500),
                                 QemuAccelSample(x=0, y=1000, z=0)],
                'tilt-back': [QemuAccelSample(x=0, y=-500, z=-900),
                              QemuAccelSample(x=0, y=-900, z=-500),
                              QemuAccelSample(x=0, y=-1000, z=0)],
                'gravity+x': [QemuAccelSample(x=1000, y=0, z=0)],
                'gravity-x': [QemuAccelSample(x=-1000, y=0, z=0)],
                'gravity+y': [QemuAccelSample(x=0, y=1000, z=0)],
                'gravity-y': [QemuAccelSample(x=0, y=-1000, z=0)],
                'gravity+z': [QemuAccelSample(x=0, y=0, z=1000)],
                'gravity-z': [QemuAccelSample(x=0, y=0, z=-1000)],
                'none': [QemuAccelSample(x=0, y=0, z=0)]
            }[args.motion]
        else:
            raise Exception("No filename specified")

        max_accel_samples = 255
        if len(samples) > max_accel_samples:
            raise ToolError("Cannot send {} samples. The max number of accel samples that can be sent at a time is "
                            "{}.".format(len(samples), max_accel_samples))
        accel_input = QemuAccel(samples=samples, count=len(samples))
        packet = QemuPacket(data=accel_input)
        packet.serialise()

        try:
            if isinstance(self.pebble.transport, ManagedEmulatorTransport):
                self.pebble.transport.send_packet(WebSocketRelayQemu(protocol=packet.protocol,
                                                                     data=accel_input.serialise()),
                                                  target=MessageTargetPhone())
            elif isinstance(self.pebble.transport, QemuTransport):
                self.pebble.transport.send_packet(accel_input, target=MessageTargetQemu())
                # target, response = self.pebble.transport.read_packet()
        except IOError as e:
            raise ToolError(str(e))

    @classmethod
    def add_parser(cls, parser):
        parser = super(EmuAccelCommand, cls).add_parser(parser)
        parser.add_argument('motion',
                            choices=['tilt-left', 'tilt-right', 'tilt-forward', 'tilt-back', 'gravity+x',
                                     'gravity-x', 'gravity+y', 'gravity-y', 'gravity+z', 'gravity-z', 'none',
                                     'custom'],
                            help="The type of accelerometer motion to send to the emulator. If using an accel file, "
                                 "specify 'custom' and then specify the filename using the '--file' option")
        parser.add_argument('--file', help="Filename of the file containing custom accel data. Each line of this text "
                                           "file should contain the comma-separated x, y, and z readings. (e.g. "
                                           "'-24, -88, -1032')")
        return parser


class EmuAppConfigCommand(PebbleCommand):
    command = 'emu-app-config'

    def __call__(self, args):
        super(EmuAppConfigCommand, self).__call__(args)
        print("Running {}...".format(self.command))

        if not args.file:
            try:
                if isinstance(self.pebble.transport, ManagedEmulatorTransport):
                    self.pebble.transport.send_packet(WebSocketPhonesimAppConfig(config=AppConfigSetup()),
                                                      target=MessageTargetPhone())
                    response = self.pebble.read_transport_message(MessageTargetPhone, WebSocketPhonesimConfigResponse)
                    print(response)
                else:
                    raise ToolError("App config is only supported over phonesim connections")
            except IOError as e:
                raise ToolError(str(e))
            config_url = response.url
        else:
            config_url = "file://{}".format(os.path.realpath(args.file))

        print(config_url)
        browser = BrowserController()
        browser.open_config_page(config_url, self.handle_config_close)

    def handle_config_close(self, query):
        if query == '':
            self.pebble.transport.send_packet(WebSocketPhonesimAppConfig(config=AppConfigCancelled()),
                                              target=MessageTargetPhone())
        else:
            self.pebble.transport.send_packet(WebSocketPhonesimAppConfig(config=AppConfigResponse(data=query)),
                                              target=MessageTargetPhone())

    @classmethod
    def add_parser(cls, parser):
        parser = super(EmuAppConfigCommand, cls).add_parser(parser)
        parser.add_argument('--file', help="Name of local file to use for settings page in lieu of URL specified in JS")
        return parser


class EmuBatteryCommand(PebbleCommand):
    command = 'emu-battery'

    def __call__(self, args):
        super(EmuBatteryCommand, self).__call__(args)
        print("Running {}...".format(self.command))
        battery_input = QemuBattery(percent=args.pct, charging=args.charging)
        packet = QemuPacket(data=battery_input)
        packet.serialise()

        try:
            if isinstance(self.pebble.transport, ManagedEmulatorTransport):
                self.pebble.transport.send_packet(WebSocketRelayQemu(protocol=packet.protocol,
                                                                     data=battery_input.serialise()),
                                                  target=MessageTargetPhone())
            elif isinstance(self.pebble.transport, QemuTransport):
                self.pebble.transport.send_packet(battery_input, target=MessageTargetQemu())
        except IOError as e:
            raise ToolError(str(e))

    @classmethod
    def add_parser(cls, parser):
        parser = super(EmuBatteryCommand, cls).add_parser(parser)
        parser.add_argument('--pct', type=int, default=80,
                            help="Set the percentage battery remaining (0 to 100) on the emulator")
        parser.add_argument('--charging', action='store_true', help="Set the Pebble emulator to charging mode")
        return parser


class EmuButtonCommand(PebbleCommand):
    command = 'emu-button'

    def __call__(self, args):
        super(EmuButtonCommand, self).__call__(args)
        print("Running {}...".format(self.command))
        state = {'back': QemuButton.Button.Back, 'up': QemuButton.Button.Up, 'select': QemuButton.Button.Select,
                 'down': QemuButton.Button.Down}[args.button]
        button_input = QemuButton(state=state)
        packet = QemuPacket(data=button_input)
        packet.serialise()

        try:
            if isinstance(self.pebble.transport, ManagedEmulatorTransport):
                self.pebble.transport.send_packet(WebSocketRelayQemu(protocol=packet.protocol,
                                                                     data=button_input.serialise()),
                                                  target=MessageTargetPhone())
            elif isinstance(self.pebble.transport, QemuTransport):
                self.pebble.transport.send_packet(button_input, target=MessageTargetQemu())
        except IOError as e:
            raise ToolError(str(e))

    @classmethod
    def add_parser(cls, parser):
        parser = super(EmuButtonCommand, cls).add_parser(parser)
        parser.add_argument('button', choices=['back', 'up', 'select', 'down'], default=None,
                            help="Send a button press to the emulator")
        return parser


class EmuBluetoothConnectionCommand(PebbleCommand):
    command = 'emu-bt-connection'

    def __call__(self, args):
        super(EmuBluetoothConnectionCommand, self).__call__(args)
        print("Running {}...".format(self.command))
        connected = args.connected == 'yes'
        bt_input = QemuBluetoothConnection(connected=connected)
        packet = QemuPacket(data=bt_input)
        packet.serialise()

        try:
            if isinstance(self.pebble.transport, ManagedEmulatorTransport):
                self.pebble.transport.send_packet(WebSocketRelayQemu(protocol=packet.protocol,
                                                                     data=bt_input.serialise()),
                                                  target=MessageTargetPhone())
            elif isinstance(self.pebble.transport, QemuTransport):
                self.pebble.transport.send_packet(bt_input, target=MessageTargetQemu())
        except IOError as e:
            raise ToolError(str(e))

    @classmethod
    def add_parser(cls, parser):
        parser = super(EmuBluetoothConnectionCommand, cls).add_parser(parser)
        parser.add_argument('--connected', choices=['no', 'yes'], default='yes',
                            help="Set the emulator BT connection status")
        return parser


class EmuCompassCommand(PebbleCommand):
    command = 'emu-compass'

    def __call__(self, args):
        super(EmuCompassCommand, self).__call__(args)
        print("Running {}...".format(self.command))
        if args.calib == 'invalid':
            calibrated = QemuCompass.Calibration.Uncalibrated
        elif args.calib == 'calibrating':
            calibrated = QemuCompass.Calibration.Refining
        else:
            calibrated = QemuCompass.Calibration.Complete

        try:
            # heading = (heading_in_degrees * max_angle_radians + 180) / max_angle_degrees
            heading = (args.heading * 0x10000 + 180) / 360
        except TypeError:
            heading = None

        compass_input = QemuCompass(heading=heading, calibrated=calibrated)
        packet = QemuPacket(data=compass_input)
        packet.serialise()

        try:
            if isinstance(self.pebble.transport, ManagedEmulatorTransport):
                self.pebble.transport.send_packet(WebSocketRelayQemu(protocol=packet.protocol,
                                                                     data=compass_input.serialise()),
                                                  target=MessageTargetPhone())
            elif isinstance(self.pebble.transport, QemuTransport):
                self.pebble.transport.send_packet(compass_input, target=MessageTargetQemu())
        except IOError as e:
            raise ToolError(str(e))

    @classmethod
    def add_parser(cls, parser):
        parser = super(EmuCompassCommand, cls).add_parser(parser)
        parser.add_argument('--heading', type=int, default=0, help="Set the emulator compass heading (0 to 359)")
        parser.add_argument('--calib', choices=['invalid', 'calibrating', 'calibrated'], default='calibrated',
                            help="Set the emulator compass calibration status")
        return parser


class EmuTapCommand(PebbleCommand):
    command = 'emu-tap'

    def __call__(self, args):
        super(EmuTapCommand, self).__call__(args)
        print("Running {}...".format(self.command))
        direction = 1 if args.direction.endswith('+') else -1

        if args.direction.startswith('x'):
            axis = QemuTap.Axis.X
        elif args.direction.startswith('y'):
            axis = QemuTap.Axis.Y
        elif args.direction.startswith('z'):
            axis = QemuTap.Axis.Z
        else:
            raise ToolError("Nice try, Pebble doesn't operate in 4-D space")

        tap_input = QemuTap(axis=axis, direction=direction)
        packet = QemuPacket(data=tap_input)
        packet.serialise()

        try:
            if isinstance(self.pebble.transport, ManagedEmulatorTransport):
                self.pebble.transport.send_packet(WebSocketRelayQemu(protocol=packet.protocol,
                                                                     data=tap_input.serialise()),
                                                  target=MessageTargetPhone())
            elif isinstance(self.pebble.transport, QemuTransport):
                self.pebble.transport.send_packet(tap_input, target=MessageTargetQemu())
        except IOError as e:
            raise ToolError(str(e))

    @classmethod
    def add_parser(cls, parser):
        parser = super(EmuTapCommand, cls).add_parser(parser)
        parser.add_argument('--direction', choices=['x+', 'x-', 'y+', 'y-', 'z+', 'z-'], default='x+',
                            help="Set the direction of the accel tap in the emulator")
        return parser