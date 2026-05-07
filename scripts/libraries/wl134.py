# PChaturvedi 2025
# Reader module: WL-134 ISO11784/85
# Microchip module: ISO11784 FDX-B
# Update: Including payload decoder for temperature

# import pyb
# uart = pyb.UART(1, baudrate=9600, timeout_char=200)

def format_id(raw_bytes):

    # ID
    # print(raw_bytes)
    try:
        data_string = raw_bytes.split(b'\x02')[1]
    except:
        data_string = raw_bytes.split(b'\x82')[1]

    try:
        data_string = data_string.split(b'\x03')[0]
    except:
        data_string = data_string.split(b'\x83')[0]

    data_part = str(data_string)[2:28]
    chars = [None]*len(data_part)

    for i in range(len(data_part)):
        chars[i] = data_part[-(i+1)]

    new_data_string = "".join(str(x) for x in chars)

    reserved_6_byte = new_data_string[0:6]
    # reserved_4_byte = new_data_string[6:10]
    # animal_flag = int(new_data_string[10], 16)
    # data_flag = int(new_data_string[11], 16)
    country = int(new_data_string[12:16], 16)
    animal_id = int(new_data_string[16:], 16)

    # Temperature
    if reserved_6_byte!="000000":
        temp_1 = list(reserved_6_byte)
        temp_1[3] = "1"
        temp = "".join(temp_1)

        # print("Temp (in HEXADECIMAL): ", temp)

        temp = int(temp, 16)
        # print("Temp (in DECIMAL): ", temp)

        tempC = (temp/10)-0.9
        tempF = (tempC*9/5)+32
    else:
        tempC = tempF = 99
    # Checksum
    valid = False
    checksum_res = str(raw_bytes[-2:-1])[-3:-1]
    checksum_res_bin = bin(int(checksum_res, 16))[2:]
    checksum_res_inv_bin = "".join("1" if i=="0" else "0" for i in checksum_res_bin)
    checksum_rhs = int(checksum_res_inv_bin, 2)

    def checksum(data):
        checksum = 0
        for i in data:
            checksum = checksum^i
        return checksum

    checksum_data = data_string[0:26]

    if tempC != 99:

        # print("Checksum data before replacement of 0: ", checksum_data)
        checksum_data = checksum_data[:22]+b'1'+checksum_data[23:]
        # print("Checksum data after replacement of 0:  ", checksum_data)

    checksum_lhs = checksum(checksum_data)

    # print(checksum_lhs, checksum_rhs)

    if checksum_lhs == checksum_rhs:
        valid = True

    return [f"{country:03d}", f"{animal_id:012d}", f"{tempC:0.1f}", f"{tempF:0.1f}", f"{valid}"]

# print("Ready to read...")

# while True:
#     try:
#         while True:
#             if uart.any()>1:
#                 raw_id = uart.read()
#                 print(f"----------\nRaw ID: {raw_id}")
#                 fid = format_id(raw_id)
#                 print(f"Country code: {fid[0]}\nID: {fid[1]}\nTemp (C): {fid[2]}\nTemp (F): {fid[3]}\nChecksum validated? {fid[4]}\n----------\n")

#     except Exception as e:
#         print(e)
