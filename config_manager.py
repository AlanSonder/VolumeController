import json
import os
import shutil
from typing import Any

from app_paths import get_app_dir
from logger import setup_logger

logger = setup_logger("VolumeController")

CONFIG_DIR = os.path.join(get_app_dir(), "config")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_CONFIG = {
    "whitelist": [
        "explorer.exe",
        "SearchHost.exe",
        "RuntimeBroker.exe",
        "ShellExperienceHost.exe",
        "ApplicationFrameHost.exe",
    ],
    "settings": {
        "check_interval_ms": 500,
        "auto_start": False,
        "muted_volume": 0,
        "restore_volume": 100,
        "enabled": True,
    },
}


class ConfigManager:
    def __init__(self, config_path: str | None = None):
        self._config_path = config_path or CONFIG_FILE
        self._config: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self._config_path):
            try:
                with open(self._config_path, "r", encoding="utf-8") as f:
                    self._config = json.load(f)
                self._migrate_defaults()
                logger.info("配置文件加载成功: %s", self._config_path)
            except (json.JSONDecodeError, IOError) as e:
                logger.error("配置文件加载失败: %s，使用默认配置", e)
                self._config = self._deep_copy(DEFAULT_CONFIG)
                self._save()
        else:
            self._config = self._deep_copy(DEFAULT_CONFIG)
            os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
            self._save()
            logger.info("已创建默认配置文件: %s", self._config_path)

    def _migrate_defaults(self) -> None:
        changed = False
        for key, value in DEFAULT_CONFIG.items():
            if key not in self._config:
                self._config[key] = self._deep_copy(value)
                changed = True
            elif isinstance(value, dict) and isinstance(self._config[key], dict):
                for sub_key, sub_value in value.items():
                    if sub_key not in self._config[key]:
                        self._config[key][sub_key] = (
                            self._deep_copy(sub_value)
                            if isinstance(sub_value, (dict, list))
                            else sub_value
                        )
                        changed = True
        if changed:
            self._save()

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logger.error("配置文件保存失败: %s", e)

    @staticmethod
    def _deep_copy(obj: Any) -> Any:
        return json.loads(json.dumps(obj))

    @property
    def whitelist(self) -> list[str]:
        return self._config.get("whitelist", [])

    @whitelist.setter
    def whitelist(self, value: list[str]) -> None:
        normalized = [name.lower().strip() for name in value if name.strip()]
        unique = list(dict.fromkeys(normalized))
        self._config["whitelist"] = unique
        self._save()
        logger.info("白名单已更新: %s", unique)

    def add_to_whitelist(self, process_name: str) -> bool:
        normalized = process_name.lower().strip()
        if not normalized:
            return False
        current = [w.lower() for w in self.whitelist]
        if normalized not in current:
            self._config["whitelist"].append(normalized)
            self._save()
            logger.info("已添加到白名单: %s", normalized)
            return True
        return False

    def remove_from_whitelist(self, process_name: str) -> bool:
        normalized = process_name.lower().strip()
        current = self._config.get("whitelist", [])
        new_list = [w for w in current if w.lower() != normalized]
        if len(new_list) < len(current):
            self._config["whitelist"] = new_list
            self._save()
            logger.info("已从白名单移除: %s", normalized)
            return True
        return False

    def is_whitelisted(self, process_name: str) -> bool:
        normalized = process_name.lower().strip()
        return normalized in [w.lower() for w in self.whitelist]

    @property
    def settings(self) -> dict[str, Any]:
        return self._config.get("settings", {})

    def get_setting(self, key: str, default: Any = None) -> Any:
        return self._config.get("settings", {}).get(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        if "settings" not in self._config:
            self._config["settings"] = {}
        self._config["settings"][key] = value
        self._save()
        logger.info("设置已更新: %s = %s", key, value)

    @property
    def enabled(self) -> bool:
        return self.get_setting("enabled", True)

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self.set_setting("enabled", value)

    @property
    def check_interval_ms(self) -> int:
        return self.get_setting("check_interval_ms", 500)

    @property
    def auto_start(self) -> bool:
        return self.get_setting("auto_start", False)

    @auto_start.setter
    def auto_start(self, value: bool) -> None:
        self.set_setting("auto_start", value)

    def export_config(self, export_path: str) -> bool:
        try:
            os.makedirs(os.path.dirname(export_path) if os.path.dirname(export_path) else ".", exist_ok=True)
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
            logger.info("配置已导出至: %s", export_path)
            return True
        except IOError as e:
            logger.error("配置导出失败: %s", e)
            return False

    def import_config(self, import_path: str) -> bool:
        try:
            with open(import_path, "r", encoding="utf-8") as f:
                new_config = json.load(f)
            if "whitelist" not in new_config or "settings" not in new_config:
                logger.error("导入的配置文件格式无效")
                return False
            backup_path = self._config_path + ".backup"
            shutil.copy2(self._config_path, backup_path)
            self._config = new_config
            self._migrate_defaults()
            self._save()
            logger.info("配置已从 %s 导入，备份保存于 %s", import_path, backup_path)
            return True
        except (json.JSONDecodeError, IOError) as e:
            logger.error("配置导入失败: %s", e)
            return False

    def reload(self) -> None:
        self._load()
        logger.info("配置已重新加载")
