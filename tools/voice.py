"""Speech backends for the local radio generator."""

from contextlib import closing
from http.client import HTTPConnection, HTTPException
from io import BytesIO
import json
import wave


LILIN = "COEIROINK:リリンちゃん"
MEI = "合成音声：HTS Voice「Mei」 © 2009–2013 名古屋工業大学（MMDAgent Project Team、CC BY 3.0）"
LILIN_STYLE = 92


def coeiroink_request(path, payload):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    try:
        with closing(HTTPConnection("127.0.0.1", 50032, timeout=60)) as connection:
            connection.request("POST", path, data, {"Content-Type": "application/json"})
            response = connection.getresponse()
            if response.status != 200:
                raise RuntimeError(f"COEIROINK {path} が HTTP {response.status} を返しました。リリンちゃんの音声モデルとバージョンを確認してください。")
            return response.read()
    except (OSError, HTTPException) as exc:
        raise RuntimeError("COEIROINK に接続できません。PC で COEIROINK v2 を起動し、リリンちゃんを追加してください。") from exc


def load_voice(config):
    if config.get("voice", "lilin") == "mei":
        import numpy as np
        import pyopenjtalk

        def speak(text):
            clip, rate = pyopenjtalk.tts(text, speed=1.07, predict_nani=False)
            if rate != 48_000:
                raise RuntimeError("Mei returned an unexpected sample rate.")
            return np.clip(clip, -32768, 32767).astype("<i2").tobytes()

        return speak, 48_000, MEI
    if config.get("voice", "lilin") != "lilin":
        raise ValueError("news.json の voice は lilin または mei を指定してください。")

    speaker = json.loads(coeiroink_request(f"/v1/style_id_to_speaker_meta?styleId={LILIN_STYLE}", {}))
    if speaker.get("speakerName") != "リリンちゃん" or speaker.get("styleName") != "メスガキ":
        raise RuntimeError("リリンちゃんの「メスガキ」スタイルを COEIROINK に追加してください。")

    def speak(text):
        data = coeiroink_request("/v1/synthesis", {
            "speakerUuid": speaker["speakerUuid"], "styleId": LILIN_STYLE,
            "text": text, "prosodyDetail": [], "speedScale": 1.0,
            "volumeScale": 1.0, "pitchScale": 0.0, "intonationScale": 1.0,
            "prePhonemeLength": 0.0, "postPhonemeLength": 0.0, "outputSamplingRate": 44_100,
            "sampledIntervalValue": 0, "adjustedF0": [],
        })
        with wave.open(BytesIO(data), "rb") as wav:
            if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (1, 2, 44_100):
                raise RuntimeError("COEIROINK returned an unexpected WAV format.")
            return wav.readframes(wav.getnframes())

    return speak, 44_100, LILIN
