import asyncio
import json
from datetime import datetime, timedelta
from configmanager import ConfigManager

class Scheduler:
    def __init__(self, config_manager, fix_engine):
        self.config_manager = config_manager
        self.fix_engine = fix_engine
        self.schedules = []
        self.connection_settings = {}
        self.load_configuration()
        self.scheduler_task = asyncio.create_task(self.run_scheduler())

    def load_configuration(self):
        # Load the schedules and connection settings from the config manager
        schedule_json = self.config_manager.get('Scheduler', 'schedules', fallback='[]')
        self.schedules = json.loads(schedule_json)
        self.connection_settings = {
            "host": self.config_manager.get('FIX', 'host', '127.0.0.1'),
            "port": int(self.config_manager.get('FIX', 'port', '5000')),
            "sender": self.config_manager.get('FIX', 'sender', 'SENDER'),
            "target": self.config_manager.get('FIX', 'target', 'TARGET')
        }

    async def start(self):
        await self.fix_engine.connect()

    async def stop(self):
        await self.fix_engine.handle_logout(None)

    async def reset(self):
        await self.fix_engine.reset_sequence_numbers()

    async def reset_start(self):
        await self.reset()
        await self.start()

    async def run_scheduler(self):
        while True:
            now = datetime.now().time()
            for task in self.schedules:
                task_time = datetime.strptime(task["time"], "%H:%M").time()
                if now >= task_time and (now - task_time) < timedelta(minutes=1):
                    action = getattr(self, task["action"], None)
                    if action:
                        await action()
            await asyncio.sleep(60)
