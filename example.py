import time
import json
import gaiaclient

CLIENT = gaiaclient.Client(
    'http://localhost:1234',
    # Callback for state changes
    # machine_state_callback=print,
)

# Get state of the tester
print("State: " + CLIENT.state)

# This is how you get properties of application.
# For example here we get current position of X-axle of main robot.
print(CLIENT.applications['MainRobot']['properties']['position']['x'])


# Print available applications and actions
class GaiaJsonEncoder(json.JSONEncoder):
    '''Encode json properly'''
    def default(self, obj):
        if callable(obj):
            return obj.__name__
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)


print(json.dumps(CLIENT.applications, indent=4, sort_keys=True, cls=GaiaJsonEncoder))
print(json.dumps(CLIENT.state_triggers, indent=4, sort_keys=True, cls=GaiaJsonEncoder))


def print_with_timestamp(msg):
    from datetime import datetime
    now = datetime.now()
    now = now.strftime("%H:%M:%S")
    print(now + ": " + msg)


while True:
    # From here starts the actual test sequence

    # Fake operator action. Put DUT in.
    CLIENT.applications['dut']['actions']['force-presence-on']()  # <-- DONT't USE IN PRODUCTION

    # Step 1: We are waiting that the test box gets ready and operator puts DUT(s) in

    # Step 2: Operator did put the DUT(s) in. DUT(s) is locked and it is safe to attach
    # battery connector, USB etc.The test box is still closing so it is
    # not audio or RF shielded and robot actions are not allowed

    # Optionally wait the test box closing
    CLIENT.wait_closing()  # <-- Optional

    print_with_timestamp("Test box closing!")

    # Wait that the test box is fully closed and ready for testing
    CLIENT.wait_ready()

    # Step 3: Test box is fully closed and we are ready for actual testing.
    print_with_timestamp("Ready for testing!")

    # Execute the tests. Here's some examples.

    # Run robot movement. See GcodeExample.GCode for g-code example and also how
    # to define tool on g-code.
    # Note that for safety reason when g-code is modified it will run once with low speed and power.
    # So if you made mistake and robot collides it won't brake anything
    # CLIENT.applications["MainRobot"]['actions']["cnc_run"](plain_text=GcodeExample.GCode)

    # Push button on DUT with pusher
    # CLIENT.applications["SideButtonPusher"]['actions']["Push"]()

    # Optionally wait that pusher is on end position (detected by sensor)
    # CLIENT.applications["SideButtonPusher"].wait_state("Push")

    # Release pusher
    # CLIENT.applications["SideButtonPusher"]['actions']["Release"]()

    # Record audio
    # (Not implemented in python CLIENT - yet!) CLIENT.applications["WaveRecorder"]['actions']["record-wave"](new Dictionary<string, object> { { "time_s", 2 }, { "filename", "testrecord.wav" } });

    # Play audio
    # (Not implemented in python CLIENT - yet!) CLIENT.Applications["WavePlayer"]['actions']["play-wave"](new Dictionary<string, object> { { "filename", "sine_1000Hz_-3dBFS_3s.wav" } });

    # Step 4: Testing is ready and we release the DUT and give test result so that test box can indicate it to operator
    CLIENT.state_triggers["ReleasePass"]()
    # The test box must be not ready after the release
    # If we don't wait here we might start the new sequence before last one is even ended
    CLIENT.wait_not_ready()
    print_with_timestamp("Test box not ready!")

    # Fake operator action. Take DUT out.
    time.sleep(2)  # <-- DO NOT USE ON PRODUCTION!
    CLIENT.applications['dut']['actions']['force-presence-off']()  # <-- DO NOT USE ON PRODUCTION!
