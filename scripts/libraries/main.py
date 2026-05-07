# WildIntel with VGA camera and WL134 scanner
# Version 14.0
# Process:
##   1 Wake up Portenta and WL134 by ATtiny85 upon motion
## 2.1 Click pics, do inference, drop bait; stay active for ACTIVE_TIME mins
## 2.2 Keep scanning for microchip
##   3 If no new motion detected for 1 min, connect to LoRaWAN and send messages, send signal to ATtiny85 to go to sleep again
##
## Updates:
##  1. Carousel power increases by 5% every 3 seconds for 12 seconds total
##  2. Custom exception handling (that sends to sleep upon error) now runs over the whole main program (including LoRaWAN)
##  3. Changed switch pin to D8 since HIGH D4 would not allow LoRaWAN to connect
##  4. Dispenser active only between 7 PM and 7 AM
##  5. Custom libraries are all lower-case now. Placed in "utils" folder
##  6. Payload changed to accomodate double-digit motion triggers (actual formatting done on Datacake)
##  7. Common APP_KEY for all devices: 589140B66691B9BB2F6074465B3F6DBB
##  8. Replaced sensor (deprecated) modules with csi
#===============================================
# SETUP
#===============================================
import sys

# Declare dispenser activity cutoff times (hour in mins) without leading zeros
DISPENSER_ON = 18*60
DISPENSER_OFF = 8*60
# DISPENSER_ON = 10*60+45
# DISPENSER_OFF = 14*60+30

try:
    # Library imports
    import machine, csi, time, ml, uos, gc, pyb, lora, random, ds1307, wl134

    # Define inbuilt-LED to identify a few statuses
    r_led = pyb.LED(1)
    g_led = pyb.LED(2)
    b_led = pyb.LED(3)

    # Send signal to ATtiny85 when process finished
    attinyrespond = pyb.Pin("D7", pyb.Pin.OUT, pyb.Pin.PULL_DOWN)

    # Datetime setup
    try:
        ds1307_dt = ds1307.DS1307(machine.SoftI2C("D10", "D9")).datetime()
        rtc = pyb.RTC()                                             # Instantiate pyb.RTC()
        rtc.datetime(ds1307_dt)                                     # Assign RTC from external module to Portenta's RTC
    except Exception:
        rtc = pyb.RTC()                                             # Instantiate pyb.RTC() with dummy values if external RTC fails

    print(rtc.datetime())

    # Flag if RTC is actually working or not based on YYYY
    if rtc.datetime()[0]>2015:
        rtc_flag = 1
    else:
        rtc_flag = 0

    # Check if now time is within working hour range or not
    def nowtime_between(now, start, end):
        if start <= end:
            return start <= now <= end
        else: # Crosses midnight
            return now >= start or now <= end

    timenow = rtc.datetime()[4] * 60 + rtc.datetime()[5]

    if rtc_flag == 1 and nowtime_between(timenow, DISPENSER_ON, DISPENSER_OFF) == False:
        print("Outside activity time range. Going to sleep")

        r_led.on()
        b_led.on()
        pyb.delay(250)
        r_led.off()
        b_led.off()

        attinyrespond.on()

    else:
        print("Within activity time range")
        # Paths
        save_path = "save"
        log_path = "log"

        try:
            # Create folders if does not exist
            paths = [save_path, log_path]
            for path in paths:
                if path not in uos.listdir():
                    uos.mkdir(path)

            # Create log file if does not exist
            if "log.csv" not in uos.listdir(log_path):
                with open(f"{log_path}/log.csv", "a") as file:
                    file.write("timestamp, event\n")

            # Create log/last_bait_dispense file if does not exist
            if "bait_log.csv" not in uos.listdir(log_path):
                with open(f"{log_path}/bait_log.csv", "a") as file:
                    file.write("timestamp\n")

        except Exception as e:
            print(e)
            r_led.on()
            g_led.on()
            b_led.on()
            pyb.delay(5000)
            attinyrespond.on()
            #Delete log folder and file to potentially fix the issue?

        # Reformat datetime for log
        def dt_format():
            return "_".join(str(i) for i in rtc.datetime()[0:3]+rtc.datetime()[4:7])

        # Register general event logs
        def logprog(event):
            with open(f"{log_path}/log.csv", "a") as file:
                if event == "Motion":
                    file.write(f"\n{dt_format()}, {event}\n")
                else:
                    file.write(f"{dt_format()}, {event}\n")

            print(event)
            pyb.delay(250)

        # Register latest bait drop datetime
        def bait_log():
            with open(f"{log_path}/bait_log.csv", "w") as file:
                file.write(f"{rtc.datetime()}\n")

            pyb.delay(250)

        # Exception handling
        def exception(e):
            r_led.on()
            g_led.on()
            b_led.on()
            logprog(e)
            pyb.delay(1000)         # Add extra delay to prevent file corruption (already a small delay in logprog)
            attinyrespond.on()

        #============================
        # Global variables
        #============================
        try:
            # LoRaWAN
            # APP_KEY imported from loraappkey library
            status = "not connected"
            BAND = lora.BAND_AS923
            JOIN_EUI = "0000000000000000"
            APP_KEY = "589140B66691B9BB2F6074465B3F6DBB"

            # Payload variables (to send via LoRaWAN)
            FID = [0, 0, 0]
            N_TRIGGER = 0
            N_DEVILS = 0
            N_BAITS_DROPPED = 0

            # Time to remain active after latest motion (milliseconds)
            ACTIVE_TIME = 2*60*1000

            # Time threshold for dispenser to pause dropping baits (minutes)
            LAST_BAIT_DISPENSE_THRESH = 30

            # Camera config
            N_PHOTOS = 10                                                   # Clicks for predictions
            ROTATE = 0                                                      # Image orientation

            # Classification parameters
            CLASS_THRESH = 0.5                                              # Threshold in probability
            N_DEVILS_THRESH = 5                                             # No. images that should predict devil

            # Number of attempts to load model (if fails in first try)
            N_ATTEMPTS = 5
        except Exception as e:
            exception(e)

        #============================
        # Setup
        #============================

        # Camera setup

        for i in range(1, 10):
            try:
                camera = csi.CSI()
                camera.reset()
                camera.pixformat(csi.GRAYSCALE)
                camera.framesize(csi.VGA)
                r_led.off()
                g_led.off()
                b_led.off()
                break
            except Exception as e:
                exception(e)

        try:
            # Infrared illuminator
            ir_lights = pyb.Pin("PJ11", pyb.Pin.OUT, pyb.Pin.PULL_DOWN)     # Pin to control IR illuminator
            ir_lights.value(0)                                              # HIGH is off (high side switch p-channel MOSFET)
                                                                            # HIGH is on  (low side switch n-channel MOSFET)
            # PIR object
            pir = pyb.Pin("PA8", pyb.Pin.IN, pull=pyb.Pin.PULL_DOWN)        # PIR sensor object

            # Carousel (motor)
            tim = pyb.Timer(8, freq=20000)                                  # Set Timer for PWM
            carousel = tim.channel(3, pyb.Timer.PWM, pin=pyb.Pin("PH15"), pulse_width_percent=100)   # Only "PH15" is to use when Shield used
            CAROUSEL_POWER = 60                                             # Initial motor power for PWM in %
            CAROUSEL_TIME_THRESH_MS = 12000                                  # In milliseconds

            # Switch
            switch = pyb.Pin("D8", pyb.Pin.IN, pyb.Pin.PULL_UP)             # Limit switch object

            # Init global var 'stop_carousel' for IRQ. This will be re-init in main loop for iterative update
            stop_carousel = 0

            # Init global var 'drop_status'. This will indicate whether motor failed or not
            drop_status = "Failure"

            # Use interrupt request to detect click/unclick
            def limit_switch(timer):
                global stop_carousel, drop_status

                if switch.value()==0:
                    stop_carousel=1
                    carousel.pulse_width_percent(100)
                    drop_status = "Success"

            timer = machine.Timer()

            def debounce_switch(pin):
                timer.init(mode=machine.Timer.ONE_SHOT, period=20, callback=limit_switch)

            # Instantiate IRQ
            switch.irq(handler=debounce_switch, trigger=pyb.Pin.IRQ_FALLING)

            # WL134 RFID reader
            uart = pyb.UART(1, baudrate=9600)

            # Invoke devil classifier
            for attempt in range(N_ATTEMPTS):
                try:
                    net = ml.Model("/rom/devil.tflite")
                    # net = ml.Model("devil.tflite")
                    break
                except Exception as e:
                    attempt+=1
                    logprog(e)
                    pass

        except Exception as e:
            exception(e)

        #===============================================
        # FUNCTIONS
        #===============================================

        # Check for microchip readings
        def check_microchip():
            global FID
            if uart.any()>1:
                # Create a buffer (larger than default 64) to store microchip data
                uart_buffer = bytearray(300)
                uart.readinto(uart_buffer)
                fid = wl134.format_id(bytes(uart_buffer[0:30]))         # Decode microchip ID
            else:
                fid = FID
            print(fid)
            return fid

        # Click pictures
        def click(n):
            global FID
            img = [None]*n                                              # Empty array of size n to store images

            ## Save with datetime as filename if RTC working and random number if not
            if rtc_flag == 1:
                time_of_motion = dt_format()                            # Datetime of motion
            else:
                time_of_motion = str(random.random()).split(".")[1]     # A random number generated here for datetime

            ir_lights.value(1)                                          # Turn on IR lights
            pyb.delay(100)

            for i in range(n):                                          # Click images, save in array and path
                g_led.on()
                img[i] = camera.snapshot().rotation_corr(z_rotation=ROTATE)
                img[i].save(f"{save_path}/{time_of_motion}_{i}.jpeg")
                g_led.off()
                pyb.delay(500)

            ir_lights.value(0)                                          # Turn off IR lights
            g_led.off()
            FID = check_microchip()                                     # Check for microchip
            return(img)

        # Inference
        def inference(images):
            ## P(devil) is calculated here
            prob = [None]*len(images)                                   # Empty array to store predictions
            for i in range(len(images)):                                # Predict using loaded model
                predict = net.predict([images[i]])[0][0][0]
                prob[i] = predict
            return([prob, len([i for i in prob if i>CLASS_THRESH])])    # Return no. images that predict devil

        # Dispense bait
        def dispense_bait():
            print("Dispensing bait")
            start = pyb.millis()                                         # Save time of process start
            time_thresh = CAROUSEL_TIME_THRESH_MS                          # Time until carousel should spin

            global N_BAITS_DROPPED, drop_status

            while stop_carousel==0 and pyb.elapsed_millis(start) <= time_thresh:# Wait for 1st unclick or until time_thresh
                r_led.on()
                g_led.on()

                if pyb.elapsed_millis(start) <= 3000:
                    carousel.pulse_width_percent(max([0, 100-CAROUSEL_POWER]))            # Start motor
                elif pyb.elapsed_millis(start) > 3000 and pyb.elapsed_millis(start) <= 6000:
                    carousel.pulse_width_percent(max([0, 100-CAROUSEL_POWER-5]))         # Increase power by 5%
                elif pyb.elapsed_millis(start) > 6000 and pyb.elapsed_millis(start) <= 9000:
                    carousel.pulse_width_percent(max([0, 100-CAROUSEL_POWER-10]))         # Increase power by 5% more
                elif pyb.elapsed_millis(start) > 6000 and pyb.elapsed_millis(start) <= time_thresh:
                    carousel.pulse_width_percent(max([0, 100-CAROUSEL_POWER-15]))         # Increase power by 5% more

            carousel.pulse_width_percent(100)                           # Stop motor
            r_led.off()
            g_led.off()

            if drop_status == "Success":
                N_BAITS_DROPPED += 1                                     # 1 bait dropped
                bait_log()

            else:
                carousel.pulse_width_percent(100)                       # Hard stop carousel to prevent faulty indefinite spinning
                N_BAITS_DROPPED = 0

            logprog(drop_status)

        # Format and prepare LoRa message to be sent (broken down because message too long with microchip data)
        def prepare_lora_message(n_trigger, n_devils, n_baits_dropped):
            return str(f"{n_trigger:02d}") + str(f"{n_devils:01d}") + str(f"{n_baits_dropped:01d}")

        def prepare_lora_message1(fid1, fid2):        # Limit payload size to 11 bytes max. Only retain last 4 digits of animal ID and temperature if applicable
            fid1 = fid1[-4:]
            fid2 = int(round(float(fid2)*10))         # Remove decimal point for payload
            return str(f"{fid1:04}") + str(f"{fid2:03}")

        # Main process program (call in main())
        def process():
            print("Motion")

            global N_TRIGGER, N_DEVILS, N_BAITS_DROPPED

            N_TRIGGER += 1

            photos = click(N_PHOTOS)                    # Click pictures
            predictions = inference(photos)             # Predict
            logprog(predictions)                        # Save results to log

            # # Create a list of duplicates using list comprehension
            # duplicates = [i for i in set(predictions[0]) if predictions[0].count(i) > 1]
            # print(duplicates)

            if predictions[1] >= N_DEVILS_THRESH:
                ## Check when was the last bait dispensed (only if RTC is working)
                if rtc_flag == 1:
                    with open(f"{log_path}/bait_log.csv") as file:
                        latest_bait_dispense = file.read()
                    try:
                        last_bait_dispense_dt = tuple(int(i) for i in latest_bait_dispense.replace("(", "").replace(")", "").split(","))
                        last_dispense_elapsed = time.mktime(rtc.datetime())-time.mktime(last_bait_dispense_dt)
                    except:
                        last_dispense_elapsed = time.mktime(rtc.datetime())

                    # dispense_bait()                                                 # Dispense bait
                    # N_DEVILS += 1

                    # Dispense bait if now > LAST_BAIT_DISPENSE_THRESH mins
                    if last_dispense_elapsed >= LAST_BAIT_DISPENSE_THRESH:
                        print(f"Time since last dispense: {last_dispense_elapsed}")
                        dispense_bait()                                                 # Dispense bait
                        N_DEVILS += 1
                    else:
                        logprog("Bait drop paused")
                else:
                    dispense_bait()                                                 # Dispense bait
                    N_DEVILS += 1

            del photos, predictions                                                # Clear some memory here
            gc.collect()


        # Main function
        def main():
            r_led.off()
            global stop_carousel, fid
            stop_carousel = 0                                        # To count unclick and stop carousel
            process()                                                # Execute system processes

        #====================
        # MAIN
        #====================

        # Initialise latest motion time
        motion_time = pyb.millis()

        try:
            ## Run main() when Portenta is woken up by ATtiny85 (first motion detection)
            main()

            ## Run main() upon further motions until time since latest motion > ACTIVE_TIME
            while pyb.elapsed_millis(motion_time) < ACTIVE_TIME:
                r_led.on()
                if pir.value()==1:                              # Motion detected
                    motion_time = pyb.millis()                  # New 'latest motion' time
                    main()

            ## Reset lights
            r_led.off()
            g_led.off()
            b_led.off()

            ## Double-check if any microchip was scanned when not executing click()
            FID = check_microchip()

            message = prepare_lora_message(N_TRIGGER,
                                           N_DEVILS,
                                           N_BAITS_DROPPED)
            if int(FID[0])>0:
                message1 = prepare_lora_message1(FID[1], FID[2])
            else:
                message1 = "x"

            logprog(str([message, message1]))

            ## Estb. LoRa connection
            for attempt in range(N_ATTEMPTS):
                print(f"Attempt {attempt} to connect to TTN")
                try:
                    b_led.on()
                    L = lora.Lora(band=BAND, poll_ms=60000, debug=False)        # Define LoRa parameters for connection
                    L.join_OTAA(JOIN_EUI, APP_KEY, timeout=10000)  # Request to connect
                    status = "connected"
                    print("\nLoRa Connected")
                    b_led.off()
                    g_led.on()
                    break
                except Exception as e:
                    attempt+=1
                    print(e)
                    b_led.off()
                    r_led.on()
                    pass

            pyb.delay(1000)
            g_led.off()
            b_led.off()

            ## Send message if connection established
            if status == "connected":
                try:
                    if L.send_data(message, True):
                        print("Message confirmed")
                        b_led.on()
                        pyb.delay(500)
                        b_led.off()
                    else:
                        print("Message wasn't confirmed")
                        r_led.on()
                        g_led.on()
                        pyb.delay(500)
                        r_led.off()
                        g_led.off()

                    if message1 != "x":
                        if L.send_data(message1, True):
                            print("Message1 confirmed")
                            b_led.on()
                            pyb.delay(500)
                            b_led.off()
                        else:
                            print("Message1 wasn't confirmed")
                            r_led.on()
                            g_led.on()
                            pyb.delay(500)
                            g_led.off()
                            r_led.off()
                except Exception as e:
                    print(e)

            ## Check if any microchip was scanned during LoRa transmission (this won't be sent over LoRaWAN but will be saved in log)
            FID = check_microchip()
            logprog(FID)

        except Exception as e:
            exception(e)

        #===============================================
        # Everything done, send a message to ATtiny85 to go to sleep
        #===============================================
        pyb.delay(2000)

        while True:
            attinyrespond.on()
            for i in [1,2,3]:
                pyb.LED(i).toggle()
                pyb.delay(500)
                pyb.LED(i).toggle()

except Exception as e:
    print(e)
    # Datetime setup
    try:
        ds1307_dt = ds1307.DS1307(machine.SoftI2C("D10", "D9")).datetime()
        rtc = pyb.RTC()                                             # Instantiate pyb.RTC()
        rtc.datetime(ds1307_dt)                                     # Assign RTC from external module to Portenta's RTC
    except Exception:
        rtc = pyb.RTC()                                             # Instantiate pyb.RTC() with dummy values if external RTC fails

    def dt_format():
        return "_".join(str(i) for i in rtc.datetime()[0:3]+rtc.datetime()[4:7])

    with open("error.log", "a") as f:
            f.write(f"\n{dt_format()}")
            sys.print_exception(e, f)

    # Send signal to ATtiny85 when process finished
    attinyrespond = pyb.Pin("D7", pyb.Pin.OUT, pyb.Pin.PULL_DOWN)
    attinyrespond.on()

    while True:
        pyb.LED(1).on()
        pyb.LED(2).on()
        pyb.LED(3).on()
        pyb.delay(200)
        pyb.LED(1).off()
        pyb.LED(2).off()
        pyb.LED(3).off()
        pyb.delay(200)
