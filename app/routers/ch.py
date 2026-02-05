import pyautogui
import time
import threading
from pynput import keyboard

# Отключаем защиту pyautogui (предохранитель от залипания)bbwwd
pyautogui.FAILSAFE = False


# Функция для выполнения последовательности нажатий
def perform_sequence():
    print("Начинаем выполнение последовательности...")

    # 1. Нажать B
    print("Нажимаем B")
    pyautogui.press('b')
    time.sleep(2)

    # 2. Зажать W на 10 секунд
    print("Зажимаем W на 10 секунд")
    pyautogui.keyDown('w')
    time.sleep(10)
    pyautogui.keyUp('w')
    time.sleep(0.5)

    # 3. W и D одновременно на 5 секунд
    print("Зажимаем W и D одновременно на 5 секунд")
    pyautogui.keyDown('w')
    pyautogui.keyDown('d')
    time.sleep(5)
    pyautogui.keyUp('w')
    pyautogui.keyUp('d')
    time.sleep(0.5)

    # 4. Два нажатия на J с задержкой 5 секунд
    print("Нажимаем J первый раз")
    pyautogui.press('pageup')
    time.sleep(5)

    print("Нажимаем J второй раз")
    pyautogui.press('pageup')
    time.sleep(0.5)

    # 5. Num 2 дважды с задержкой 5 секунд
    print("Нажимаем Num 2 первый раз")
    pyautogui.press('num2')  # Или используйте '2' если num2 не работает
    time.sleep(5)

    print("Нажимаем Num 2 второй раз")
    pyautogui.press('num2')  # Или используйте '2' если num2 не работает

    print("Последовательность выполнена!")


# Функция для обработки горячих клавиш
def on_press(key):
    try:
        # Останавливаем программу при нажатии Ctrl+Shift+Q
        if key == keyboard.KeyCode.from_char('q') and \
                (keyboard.Controller().pressed(keyboard.Key.ctrl_l) or \
                 keyboard.Controller().pressed(keyboard.Key.ctrl_r)) and \
                (keyboard.Controller().pressed(keyboard.Key.shift) or \
                 keyboard.Controller().pressed(keyboard.Key.shift_r)):
            print("\nПрограмма остановлена пользователем")
            return False
    except:
        pass


# Функция для основного цикла
def main_loop():
    print("Программа запущена. Для остановки нажмите Ctrl+Shift+Q")
    print("Первое выполнение начнется через 5 секунд...")
    time.sleep(5)

    while True:
        perform_sequence()
        print(f"Ждем 130 секунд до следующего выполнения... ({time.strftime('%H:%M:%S')})")

        # Ожидание 90 секунд (с проверкой прерывания каждую секунду)
        for i in range(130):
            time.sleep(1)


# Запускаем слушатель горячих клавиш в отдельном потоке
listener = keyboard.Listener(on_press=on_press)
listener.start()

# Запускаем основной цикл
main_loop()
