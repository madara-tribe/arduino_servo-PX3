
go here https://www.arduino.cc/en/software/
and download <linux appimage>
右クリック＝＞プロパティ＝＞プログラムとして実行＝＞閉じる
# install
add-apt-repository universe
apt install libfuse2
pip3 install pyserial

# 1 preference =>　Language[日本語]
https://github.com/esp8266/Arduino
Boards Manager link: https://arduino.esp8266.com/stable/package_esp8266com_index.json
copy to [Additional boards manager URLs:].
push [OK]

# 2
tools => board => board manager => esp8266 => ”Generic ESP8266 Module”

# 3
insert real Arduino UNO

#4 
tools => port => select board path '/dev/ttyACM0'

# 5
tools => boards => ARduino AVR boards => Arduino UNO

# 6
tools => 書き込み装置=> USBash

# uninstall
rm -r /home/<user>/.arduinoIDE
