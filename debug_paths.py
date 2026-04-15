import os
import sys

print("Python version:", sys.version)
print("sys.executable:", sys.executable)
print("sys.argv[0]:", sys.argv[0])
print("os.getcwd():", os.getcwd())
print("os.path.abspath(__file__):", os.path.abspath(__file__))
print("os.path.dirname(sys.executable):", os.path.dirname(sys.executable))
print("os.path.dirname(os.path.abspath(__file__)):", os.path.dirname(os.path.abspath(__file__)))

# 模拟 app_paths.py 逻辑
if getattr(sys, 'frozen', False):
    print("\nFROZEN mode:")
    app_dir = os.path.dirname(sys.executable)
    print("app_dir (from sys.executable):", app_dir)
else:
    print("\nNON-FROZEN mode:")
    app_dir = os.path.dirname(os.path.abspath(__file__))
    print("app_dir (from __file__):", app_dir)

# 测试配置和日志目录路径
config_dir = os.path.join(app_dir, "config")
logs_dir = os.path.join(app_dir, "logs")

print("\nExpected paths:")
print("config_dir:", config_dir)
print("logs_dir:", logs_dir)

# 测试创建目录
print("\nTesting directory creation...")
try:
    os.makedirs(config_dir, exist_ok=True)
    print("Created config_dir:", config_dir)
    test_config_file = os.path.join(config_dir, "test.json")
    with open(test_config_file, "w") as f:
        f.write('{"test": "ok"}')
    print("Created test config file:", test_config_file)
    
    os.makedirs(logs_dir, exist_ok=True)
    print("Created logs_dir:", logs_dir)
    test_log_file = os.path.join(logs_dir, "test.log")
    with open(test_log_file, "w") as f:
        f.write("Test log entry")
    print("Created test log file:", test_log_file)
    
    print("\nSUCCESS: All paths work correctly!")
except Exception as e:
    print(f"\nERROR: {e}")

print("\nPress Enter to exit...")
input()
