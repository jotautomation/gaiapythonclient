import time
import gaiaclient

client = gaiaclient.Client('localhost:1234')

# Get state of the tester
print("State: " + client.state)

# This is how you get properties of application.
# For example here we get current position of X-axle of main robot.
print(client.applications["mainrobot"].properties["position"]["x"])

while True:
    # From here starts the actual test sequence

    # Step 1: We are waiting that the test box gets ready and operator puts DUT(s) in
    # (Todo: implement waiting witht out polling)
    while not client.test_box_closing or client.ready_for_testing:
        time.sleep(0.01)

    # Step 2: Operator did put the DUT(s) in. DUT(s) is locked and it is safe to attach
    # battery connector, USB etc.The test box is still closing so it is
    # not audio or RF shielded and robot actions are not allowed

    print("Test box closing!")

    # Wait that the test box is closed and ready for testing
    # (Todo: implement waiting witht out polling)
    while not client.ready_for_testing:
        time.sleep(0.01)

    # Step 3: Test box is fully closed and we are ready for actual testing.
    print("Ready for testing!")

    # Execute the tests. Here's some examples.

    # Change robot tool. Note! Tool change can be defined also in G-code
    # but some time you can save time by changing the tool
    # while doing something else.
    client.applications["MainRobot"].actions["changeTo-AudioTool"]()

    # Run robot movement. See GcodeExample.GCode for g-code example and also how
    # to define tool on g-code.
    # Note that for safety reason when g-code is modified it will run once with low speed and power.
    # So if you made mistake and robot collides it won't brake anything
    client.applications["MainRobot"].actions["cnc_run"](plain_text=GcodeExample.GCode)

    # Push button on DUT with pusher
    client.applications["SideButtonPusher"].actions["Push"]()

    # Optionally wait that pusher is on end position (detected by sensor)
    client.applications["SideButtonPusher"].wait_state("Push")

    # Release pusher
    client.applications["SideButtonPusher"].actions["Release"]()

    # Record audio
    # (Not implemented in python client - yet!) client.applications["WaveRecorder"].actions["record-wave"](new Dictionary<string, object> { { "time_s", 2 }, { "filename", "testrecord.wav" } });

    # Play audio
    # (Not implemented in python client - yet!) client.Applications["WavePlayer"].Actions["play-wave"](new Dictionary<string, object> { { "filename", "sine_1000Hz_-3dBFS_3s.wav" } });


    # Step 4: Testing is ready and we release the DUT and give test result so that test box can indicate it to operator
    # (Not implemented in python client - yet!) client.state_triggers["Release"](new Dictionary<string, object> { { "testResult1", "pass" }, { "testResult2", "pass" }, { "testResult3", "fail" } })

