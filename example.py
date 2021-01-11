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

# This is how you can download the recorded wave file from gaia machine.
CLIENT.download_wave_file('sine_1000Hz_-3dBFS_3s.wav', 'sine_1000Hz_-3dBFS_3s.wav')

# And this is how file is uploaded. The file can be later played on the machine.
CLIENT.upload_wave_file('sine_1000Hz_-3dBFS_3s.wav')


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

    #### How to run actions for applications ####

    # Let's say you have stateful application called CameraLight that has actions
    # set-LightOn and set-LightOff. Obviously first sets light on and later set light off.
    # There is a general way to run any action. For the example application it would go like this:

    # Set light on
    CLIENT.applications["CameraLight"]['actions']["set-LightOn"]()

    # Set light off
    CLIENT.applications["CameraLight"]['actions']["set-LightOff"]()

    # The above methods works for any application
    # If fields need to be set for action, it is done like this:

    # Record audio
    CLIENT.applications["WaveRecorder"]['actions']["record-wave"](time_s=2, filename='testrecord.wav')

    # Play audio
    CLIENT.applications["WavePlayer"]['actions']["play-wave"](filename='sine_1000Hz_-3dBFS_3s.wav')

    #### Waiting application state ####

    # wait_app_state() waits that the application reaches the wanted state
    CLIENT.wait_app_state('CameraLight', 'LightOn')
    CLIENT.wait_app_state('WavePlayer', 'Ready')

    #### Convenience methods ####

    # Some times you need to set stateful application state and wait that it is reached.
    # This is especially case on mechanical movements. Setting and waiting can be done
    # with single set_app_state() method

    # Set camera light on and wait that it is on
    CLIENT.set_app_state('CameraLight', 'LightOn')

    # Main robot movements can be also run and waited with single command
    import example_gcode
    CLIENT.run_main_robot(example_gcode.GCODE)

    # Step 4: Testing is ready and we release the DUT and give test result so that test box can indicate it to operator
    CLIENT.state_triggers["ReleasePass"]()
    # The test box must be not ready after the release
    # If we don't wait here we might start the new sequence before last one is even ended
    CLIENT.wait_not_ready()
    print_with_timestamp("Test box not ready!")

    # Fake operator action. Take DUT out.
    time.sleep(2)  # <-- DO NOT USE ON PRODUCTION!
    CLIENT.applications['dut']['actions']['force-presence-off']()  # <-- DO NOT USE ON PRODUCTION!
