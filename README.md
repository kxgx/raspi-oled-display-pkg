# raspi-oled-display-pkg
适配树莓派5的i2c oled中文系统信息显示程序
程序由AI生成，已经过测试

## 安装包打包
git clone https://github.com/kxgx/raspi-oled-display-pkg.git

sudo dpkg-deb --build raspi-oled-display-pkg

## 下载
由于最新版换成PyInstaller转换二进制可执行文件方式，文件体积太大仓库上传不了，只能上传到发布页

所以最新版直接下载安装包安装即可，想要进行最新版打包需要在发布页下载对应文件进行替换才能打包最新版

## 安装
wget https://github.com/kxgx/raspi-oled-display-pkg/releases/download/v1.1.1/raspi-oled-display-pkg.deb
sudo dpkg -i raspi-oled-display-pkg.deb
