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
import ntplib
import socket

# 配置文件路径
CONFIG_FILE = "/etc/oled-display.conf"

def log_error(message):
    with open("/tmp/oled-display.log", "a") as f:
        try:
            f.write(f"{datetime.datetime.now()}: {message}\n")
        except:
            pass  # 如果日志写入失败也不影响主程序运行

def load_config():
    config = configparser.ConfigParser()
    try:
        if os.path.exists(CONFIG_FILE):
            config.read(CONFIG_FILE)
            return {
                'width': int(config.get('DISPLAY', 'width', fallback=128)),
                'height': int(config.get('DISPLAY', 'height', fallback=32)),
                'scroll_speed': float(config.get('DISPLAY', 'scroll_speed', fallback=0.1)),
                'ntp_server': config.get('TIME', 'ntp_server', fallback='ntp.ntsc.ac.cn'),
                'timeout': int(config.get('TIME', 'timeout', fallback=3))
            }
    except Exception as e:
        log_error(f"配置加载失败: {str(e)}")
    return {'width': 128, 'height': 32, 'scroll_speed': 0.1,
            'ntp_server': 'ntp.ntsc.ac.cn', 'timeout': 3}

def sync_time(config):
    """时间同步函数"""
    try:
        client = ntplib.NTPClient()
        response = client.request(config['ntp_server'], timeout=config['timeout'])
        ntp_time = datetime.datetime.fromtimestamp(response.tx_time)
        subprocess.run(['sudo', 'date', '-s', ntp_time.strftime('%Y-%m-%d %H:%M:%S')], check=True)
        return "时间同步: 成功"
    except (ntplib.NTPException, socket.gaierror, subprocess.CalledProcessError) as e:
        log_error(f"NTP同步失败: {str(e)}")
        try:
            subprocess.run(['sudo', 'hwclock', '--hctosys'], check=True)
            return "时间同步: RTC成功"
        except subprocess.CalledProcessError as e:
            log_error(f"RTC同步失败: {str(e)}")
            return "时间同步: 失败"

def main():
    try:
        config = load_config()
        scroll_pos = {}  # 存储各行的滚动位置
        
        # 初始化时间同步状态
        time_sync_status = sync_time(config)
        last_sync_time = time.time()

        # 初始化显示设备（增加重试机制）
        for _ in range(3):
            try:
                serial = i2c(port=1, address=0x3C)
                device = ssd1306(serial, width=config['width'], height=config['height'])
                break
            except Exception as e:
                log_error(f"显示初始化尝试失败: {str(e)}")
                time.sleep(2)
        else:
            raise RuntimeError("显示初始化3次尝试均失败")

        # 字体配置
        def load_font():
            try:
                return ImageFont.truetype("wqy-microhei.ttc", 12)
            except:
                try:
                    return ImageFont.truetype("arial.ttf", 12)
                except:
                    return ImageFont.load_default()

        font = load_font()

        # 计算屏幕可显示行数
        def calculate_lines():
            left, top, right, bottom = font.getbbox("测试")
            text_height = bottom - top
            return config['height'] // (text_height + 2)  # 行间距2像素

        max_lines = calculate_lines()

        # 信息获取函数
        def get_system_info():
            now = datetime.datetime.now()
            try:
                # 获取CPU温度并转换为中文单位
                cpu_temp = subprocess.getoutput("vcgencmd measure_temp | cut -d= -f2")
                cpu_temp = cpu_temp.replace("'C", "").strip()
                cpu_temp = f"{float(cpu_temp):.1f}摄氏度"
            except:
                cpu_temp = "N/A"
            
            return {
                "IP地址": subprocess.getoutput("hostname -I | awk '{print $1}'"),
                "当前日期": now.strftime("%Y年%m月%d日"),
                "当前时间": now.strftime("%H时%M分%S秒"),
                "时间同步": time_sync_status,
                "CPU负载": subprocess.getoutput("top -bn1 | grep load | awk '{printf \"%.1f\", $(NF-2)}'") + "%",
                "CPU温度": cpu_temp,
                "内存使用": subprocess.getoutput("free -m | awk 'NR==2{printf \"%d/%dMB\", $3,$2}'"),
                "存储空间": subprocess.getoutput("df -h | awk '$NF==\"/\"{printf \"%s/%s\", $3,$2}'")
            }

        # 信息分组策略（保持时间日期相邻）
        def group_infos(info_dict):
            groups = []
            all_items = list(info_dict.items())
            
            date_index = 1
            time_index = 2
            sync_index = 3
            
            i = 0
            while i < len(all_items):
                group = {}
                if i == date_index:
                    group[all_items[date_index][0]] = all_items[date_index][1]
                    group[all_items[time_index][0]] = all_items[time_index][1]
                    group[all_items[sync_index][0]] = all_items[sync_index][1]
                    i = sync_index + 1
                    remaining_lines = max_lines - 3
                else:
                    remaining_lines = max_lines
                
                for item in all_items[i:i+remaining_lines]:
                    group[item[0]] = item[1]
                i += remaining_lines
                
                groups.append(group)
                scroll_pos[len(groups)-1] = {}
            return groups

        # 绘制显示内容（添加滚动功能）
        def draw_info(draw, info_group, group_index, y_offset=0):
            for i, (key, value) in enumerate(info_group.items()):
                text = f"{key}: {value}"
                text_width = font.getlength(text)
                
                if i not in scroll_pos[group_index]:
                    scroll_pos[group_index][i] = 0
                
                if text_width > config['width']:
                    scroll_pos[group_index][i] -= 1
                    if scroll_pos[group_index][i] < -text_width:
                        scroll_pos[group_index][i] = config['width']
                    x = scroll_pos[group_index][i]
                else:
                    x = (config['width'] - text_width) // 2
                
                left, top, right, bottom = font.getbbox("测试")
                y = y_offset + i*(bottom + 2)
                
                draw.text((x, y), text, font=font, fill=255)

        info_groups = group_infos(get_system_info())
        current_group = 0
        last_scroll_time = time.time()

        while True:
            current_time = time.time()
            
            # 每6小时同步一次时间
            if current_time - last_sync_time > 21600:
                time_sync_status = sync_time(config)
                info_groups = group_infos(get_system_info())
                last_sync_time = current_time
            
            if current_time - last_scroll_time > config['scroll_speed']:
                image = Image.new("1", (config['width'], config['height']))
                draw = ImageDraw.Draw(image)
                draw_info(draw, info_groups[current_group], current_group)
                device.display(image)
                last_scroll_time = current_time
            
            if current_time % 10 < 0.1:
                info_groups = group_infos(get_system_info())
            
            if current_time % 5 < 0.1:
                current_group = (current_group + 1) % len(info_groups)
            
            time.sleep(0.1)

    except KeyboardInterrupt:
        device.clear()
    except Exception as e:
        log_error(f"主循环错误: {str(e)}\n{traceback.format_exc()}")

if __name__ == "__main__":
    main()
