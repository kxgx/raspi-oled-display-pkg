#!/usr/bin/env python3
import time
import sys
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from PIL import Image, ImageDraw, ImageFont
import subprocess
import datetime
import configparser
import os
import traceback

# 配置文件路径
CONFIG_FILE = "/etc/oled-display.conf"

def log_error(message):
    with open("/tmp/oled-display.log", "a") as f:
        f.write(f"{datetime.datetime.now()}: {message}\n")

def load_config():
    config = configparser.ConfigParser()
    try:
        if os.path.exists(CONFIG_FILE):
            config.read(CONFIG_FILE)
            return {
                'width': int(config.get('DISPLAY', 'width', fallback=128)),
                'height': int(config.get('DISPLAY', 'height', fallback=32))
            }
    except Exception as e:
        log_error(f"Config load failed: {str(e)}")
    return {'width': 128, 'height': 32}

def main():
    try:
        config = load_config()
        
        # 初始化显示设备（增加重试机制）
        for _ in range(3):
            try:
                serial = i2c(port=1, address=0x3C)
                device = ssd1306(serial, width=config['width'], height=config['height'])
                break
            except Exception as e:
                log_error(f"Display init attempt failed: {str(e)}")
                time.sleep(2)
        else:
            raise RuntimeError("Display initialization failed after 3 attempts")

        # 字体配置
        def load_font():
            try:
                return ImageFont.truetype("wqy-microhei.ttc", 12)
            except:
                return ImageFont.load_default()

        font = load_font()

        # 计算屏幕可显示行数
        def calculate_lines():
            left, top, right, bottom = font.getbbox("测试")
            text_height = bottom - top
            return config['height'] // (text_height + 2)  # 行间距2像素

        max_lines = calculate_lines()
        print(f"当前屏幕可显示 {max_lines} 行信息")

        # 信息获取函数（时间日期分离）
        def get_system_info():
            now = datetime.datetime.now()
            return {
                "IP地址": subprocess.getoutput("hostname -I | awk '{print $1}'"),
                "当前日期": now.strftime("%Y年%m月%d日"),
                "当前时间": now.strftime("%H:%M:%S"),
                "CPU负载": subprocess.getoutput("top -bn1 | grep load | awk '{printf \"%.1f\", $(NF-2)}'"),
                "CPU温度": subprocess.getoutput("vcgencmd measure_temp | cut -d= -f2").replace("'C", "℃"),
                "内存使用": subprocess.getoutput("free -m | awk 'NR==2{printf \"%d/%dMB\", $3,$2}'"),
                "存储空间": subprocess.getoutput("df -h | awk '$NF==\"/\"{printf \"%s/%s\", $3,$2}'")
            }

        # 信息分组策略（保持时间日期相邻）
        def group_infos(info_dict):
            groups = []
            all_items = [
                ("IP地址", info_dict["IP地址"]),
                ("当前日期", info_dict["当前日期"]),
                ("当前时间", info_dict["当前时间"]),
                ("CPU负载", info_dict["CPU负载"]),
                ("CPU温度", info_dict["CPU温度"]),
                ("内存使用", info_dict["内存使用"]),
                ("存储空间", info_dict["存储空间"])
            ]
            
            # 确保时间日期在同一屏显示
            for i in range(0, len(all_items), max_lines):
                group = {}
                # 特殊处理确保日期时间不分开
                if i <= 1 and (i + max_lines) > 2:
                    group[all_items[1][0]] = all_items[1][1]
                    group[all_items[2][0]] = all_items[2][1]
                    remaining_lines = max_lines - 2
                    for item in all_items[3:3+remaining_lines]:
                        group[item[0]] = item[1]
                    groups.append(group)
                else:
                    for item in all_items[i:i+max_lines]:
                        group[item[0]] = item[1]
                    groups.append(group)
            
            return groups

        # 绘制显示内容
        def draw_info(draw, info_group, y_offset=0):
            for i, (key, value) in enumerate(info_group.items()):
                text = f"{key}: {value}"
                # 自动缩放文本
                while font.getlength(text) > config['width'] - 4:
                    text = text[:-1]
                x = (config['width'] - font.getlength(text)) // 2
                left, top, right, bottom = font.getbbox("测试")
                draw.text((x, y_offset + i*(bottom + 2)), text, font=font, fill=255)

        info_groups = group_infos(get_system_info())
        current_group = 0
        
        while True:
            image = Image.new("1", (config['width'], config['height']))
            draw = ImageDraw.Draw(image)
            draw_info(draw, info_groups[current_group])
            device.display(image)
            current_group = (current_group + 1) % len(info_groups)
            time.sleep(3)

    except KeyboardInterrupt:
        device.clear()
    except Exception as e:
        log_error(f"Main loop error: {str(e)}\n{traceback.format_exc()}")

if __name__ == "__main__":
    main()
