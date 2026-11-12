"""Idempotently configure microphone permission after `flutter create`."""
from pathlib import Path
root = Path(__file__).resolve().parents[1] / 'apps' / 'client'
android = root / 'android' / 'app' / 'src' / 'main' / 'AndroidManifest.xml'
if android.exists():
    xml = android.read_text()
    permission = '<uses-permission android:name="android.permission.RECORD_AUDIO" />'
    if permission not in xml:
        xml = xml.replace('<application', '    ' + permission + '\n    <application', 1)
        android.write_text(xml)
    print('Configured Android microphone permission')
ios = root / 'ios' / 'Runner' / 'Info.plist'
if ios.exists():
    xml = ios.read_text()
    if '<key>NSMicrophoneUsageDescription</key>' not in xml:
        xml = xml.replace('</dict>', '    <key>NSMicrophoneUsageDescription</key>\n'
            '    <string>Record speech to transcribe messages locally.</string>\n</dict>', 1)
        ios.write_text(xml)
    print('Configured iOS microphone permission')
