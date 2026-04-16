import os
import sys
import winreg


def add_to_startup():
    """添加到开机自启"""
    try:
        # 获取当前可执行文件路径
        if getattr(sys, 'frozen', False):
            # 打包后的可执行文件
            exe_path = sys.executable
        else:
            # 开发环境
            exe_path = os.path.abspath(__file__)
        
        # 打开注册表
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r'Software\Microsoft\Windows\CurrentVersion\Run',
            0,
            winreg.KEY_SET_VALUE
        )
        
        # 设置开机自启
        winreg.SetValueEx(
            key,
            'VolumeController',
            0,
            winreg.REG_SZ,
            f'"{exe_path}"'
        )
        
        winreg.CloseKey(key)
        print("已添加到开机自启")
        return True
    
    except Exception as e:
        print(f"添加开机自启失败: {e}")
        return False


def remove_from_startup():
    """从开机自启中移除"""
    try:
        # 打开注册表
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r'Software\Microsoft\Windows\CurrentVersion\Run',
            0,
            winreg.KEY_SET_VALUE
        )
        
        # 删除开机自启项
        winreg.DeleteValue(key, 'VolumeController')
        
        winreg.CloseKey(key)
        print("已从开机自启中移除")
        return True
    
    except FileNotFoundError:
        print("开机自启项不存在")
        return True
    except Exception as e:
        print(f"移除开机自启失败: {e}")
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="设置 VolumeController 开机自启")
    parser.add_argument('--add', action='store_true', help="添加到开机自启")
    parser.add_argument('--remove', action='store_true', help="从开机自启中移除")
    
    args = parser.parse_args()
    
    if args.add:
        add_to_startup()
    elif args.remove:
        remove_from_startup()
    else:
        print("请指定 --add 或 --remove 参数")