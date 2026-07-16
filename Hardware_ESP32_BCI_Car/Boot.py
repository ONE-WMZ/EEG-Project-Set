import network
import machine
import time
import json
import socket
import uasyncio as asyncio
import neopixel  

try:
    from microdot import Microdot
except ImportError:
    print("[Error] microdot 模块未找到！请上传 microdot.py")
    raise


web_IP = "192.168.0.1"

# SSID = "ONE."
# PASSWORD = "123456789"


#  电机参数
SPEED = 750
# 最大 PWM 占空比（0~1023）
MOTOR_FREQ = 1000          # PWM 频率（Hz）
FORWARD_DURATION = 0.8     # 前进/后退持续时间（秒）
TURN_DURATION = 0.05       # 转向持续时间（秒）

# TB6612FNG 引脚定义
AIN1 = machine.Pin(9, machine.Pin.OUT)
AIN2 = machine.Pin(46, machine.Pin.OUT)
BIN1 = machine.Pin(11, machine.Pin.OUT)
BIN2 = machine.Pin(12, machine.Pin.OUT)

PWMA = machine.PWM(machine.Pin(3), freq=MOTOR_FREQ)
PWMB = machine.PWM(machine.Pin(13), freq=MOTOR_FREQ)

STBY = machine.Pin(10, machine.Pin.OUT)
STBY.value(1)  # 使能驱动

def stop_motors():
    AIN1.off(); AIN2.off()
    BIN1.off(); BIN2.off()
    PWMA.duty(0); PWMB.duty(0)

stop_motors()

# RGB LED 配置（GPIO 48）
RGB_PIN = 48
np = neopixel.NeoPixel(machine.Pin(RGB_PIN), 1)  # 1 颗灯珠

# 颜色定义
RED    = (255, 0, 0)    # 红
GREEN  = (0, 255, 0)    # 绿
YELLOW = (255, 255, 0)  # 黄
OFF    = (0, 0, 0)      # 关

def rgb_off():
    np[0] = OFF
    np.write()

async def blink_rgb(color, times=1, on_ms=100, off_ms=100):
    for _ in range(times):
        np[0] = color
        np.write()
        await asyncio.sleep_ms(on_ms)
        np[0] = OFF
        np.write()
        await asyncio.sleep_ms(off_ms)

#  软启停辅助函数 
async def ramp_speed(pwm_a, pwm_b, start_duty, end_duty, duration=0.5, steps=20):
    # 平滑调整 PWM 占空比
    if start_duty == end_duty:
        pwm_a.duty(end_duty)
        pwm_b.duty(end_duty)
        return

    step_delay = duration / steps
    delta = (end_duty - start_duty) / steps

    for i in range(steps + 1):
        duty = int(start_duty + delta * i)
        duty = max(0, min(1023, duty))  # 限制在有效范围
        pwm_a.duty(duty)
        pwm_b.duty(duty)
        await asyncio.sleep(step_delay)

#  全局状态 
current_action = None
current_task = None
ip_address = None 

#  动作执行逻辑（带软启停）
async def run_action(action):
    global current_action
    current_action = action

    try:
        # 设置电机方向
        if action == "forward":
            AIN1.on(); AIN2.off()
            BIN1.on(); BIN2.off()
        elif action == "backward":
            AIN1.off(); AIN2.on()
            BIN1.off(); BIN2.on()
        elif action == "left":
            AIN1.off(); AIN2.on()    # 左轮正转
            BIN1.on();  BIN2.off()   # 右轮反转
        elif action == "right":
            AIN1.on();  AIN2.off()   # 左轮反转
            BIN1.off(); BIN2.on()    # 右轮正转
        elif action == "stop":
            current_duty = PWMA.duty()
            await ramp_speed(PWMA, PWMB, current_duty, 0, duration=0.3)
            stop_motors()
            current_action = None
            return
        else:
            stop_motors()
            current_action = None
            return

        #  软启动
        await ramp_speed(PWMA, PWMB, 100, SPEED, duration=0.5)

        # 保持运行
        move_time = FORWARD_DURATION if action in ("forward", "backward") else TURN_DURATION
        await asyncio.sleep(move_time)

        #  软停止
        await ramp_speed(PWMA, PWMB, SPEED, 0, duration=0.3)

    except asyncio.CancelledError:
        current_duty = PWMA.duty()
        await ramp_speed(PWMA, PWMB, current_duty, 0, duration=0.2)
        stop_motors()
        current_action = None
        return

    stop_motors()
    current_action = None


#  Web API 服务 
app = Microdot()

@app.route('/cmd', methods=['POST'])
async def cmd(request):
    global current_task

    action = request.json.get("action") if request.json else None
    valid_actions = {"forward", "backward", "left", "right", "stop"}
    if not action or action not in valid_actions:
        return {"error": "Invalid action"}, 400

    print("[New]:", action)
    await blink_rgb(YELLOW, times=1, on_ms=150, off_ms=0)  #  黄灯闪一次

    if current_task is not None:
        current_task.cancel()
        current_task = None

    current_task = asyncio.create_task(run_action(action))
    return {"status": "executing", "action": action}


@app.route('/ping')
def ping(request):
    return {
        "status": "alive",
        "ip": ip_address,
        "current_action": current_action
    }


@app.route('/')
def home(request):
    return "ESP32 小车 API 已就绪！"


#  向主控服务器发送就绪通知
def send_ready_notification():
    try:
        payload = {"status": "ready", "device": "esp32_car", "ip": ip_address}
        body = json.dumps(payload)
        request = (
            f"POST /notify HTTP/1.1\r\n"
            f"Host: {web_IP}:5000\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n\r\n"
            + body
        )
        addr = socket.getaddrinfo(web_IP, 5000)[0][-1]
        s = socket.socket()
        s.settimeout(3)
        s.connect(addr)
        s.send(request.encode('utf-8'))
        s.close()
        print("[OK] 就绪通知已发送")
    except Exception as e:
        print("[Error] 通知发送失败:", e)


#  主程序入口
async def main():
    global ip_address

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    # 未联网：红灯慢闪
    print("[Runing] 正在连接 WiFi...")
    blink_task = asyncio.create_task(blink_rgb(RED, times=1000, on_ms=100, off_ms=100))

    wlan.connect(SSID, PASSWORD)
    while not wlan.isconnected():
        await asyncio.sleep(0.1)

    #  联网成功：停止红闪，绿闪 4 次
    blink_task.cancel()
    rgb_off()
    await blink_rgb(GREEN, times=4, on_ms=100, off_ms=100)
    rgb_off()

    ip_address = wlan.ifconfig()[0]
    print("[OK] ESP32 IP 地址:", ip_address)

    send_ready_notification()

    print("[OK] 启动 Web 服务 (http://{}:80)...".format(ip_address))
    await app.start_server(port=80)


# 启动异步事件循环 
try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("[Stop] 手动停止")
    stop_motors()
    rgb_off()
