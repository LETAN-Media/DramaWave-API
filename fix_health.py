import os

for provider in ['reelshort', 'goodshort']:
    path = f'app/providers/{provider}/provider.py'
    with open(path, 'r') as f:
        content = f.read()
    
    if 'def average_latency(self) -> float:' not in content:
        content = content.replace('    def record_success', '''    @property
    def average_latency(self) -> float:
        if self.success_count == 0:
            return 0.0
        return self.total_latency / self.success_count

    @property
    def failure_rate(self) -> float:
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.0
        return self.failure_count / total

    def record_success''')
        with open(path, 'w') as f:
            f.write(content)
            
