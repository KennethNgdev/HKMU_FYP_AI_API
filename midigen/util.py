#Source from https://github.com/dbjohnson/midigen
import math
import os
import tempfile
import pretty_midi

from midigen.notes import Note
from midigen.keys import Key, Mode
from midigen.time import TimeSignature, Measure
from midigen.sequencer import Song, Track


def parse_mode(mode_str: str) -> Mode:
    """
    根據輸入字串返回對應的 Mode 對象
    """
    mode_str = mode_str.lower().strip()
    if mode_str == "major":
        return Mode.Major
    elif mode_str == "minor":
        return Mode.Minor
    else:
        raise ValueError(f"不支持的調式：{mode_str}")


def note_from_string(note_str: str) -> Note:
    """
    根據輸入字串返回對應的 Note 對象（目前只處理基礎音名）
    """
    note_str = note_str.strip().upper()
    if note_str == "C":
        return Note.C
    elif note_str == "D":
        return Note.D
    elif note_str == "E":
        return Note.E
    elif note_str == "F":
        return Note.F
    elif note_str == "G":
        return Note.G
    elif note_str == "A":
        return Note.A
    elif note_str == "B":
        return Note.B
    else:
        raise ValueError(f"不支持的音符：{note_str}")


def get_midi_info(input_midi_file: str):
    """
    讀取 MIDI 文件，並返回估計的 BPM 與文件總時長（秒）
    """
    try:
        midi_data = pretty_midi.PrettyMIDI(input_midi_file)
        estimated_tempo = midi_data.estimate_tempo()
        duration = midi_data.get_end_time()
        print(f"從 {input_midi_file} 估計 BPM 為: {estimated_tempo:.2f}")
        print(f"MIDI 文件時長: {duration:.2f} 秒")
        return int(round(estimated_tempo)), duration
    except Exception as e:
        raise RuntimeError(f"讀取 MIDI 文件出錯: {e}")

def get_midi_key(input_midi_file: str, default_key: str = "C") -> str:
    """
    嘗試從 MIDI 文件中讀取 Key Signature 事件，
    並根據 key_number 返回一個調性字串。
    如果沒有找到，則返回 default_key 參數指定的預設值。
    
    pretty_midi 中的 key_signature_changes 屬性返回的 Event
    通常包含 key_number 屬性，範圍約在 -7 到 7：
      - 正數代表升號數量 (例如 1 -> G 大調、2 -> D 大調)
      - 負數代表降號數量 (例如 -1 -> F 大調、-2 -> Bb 大調)
    """
    import pretty_midi
    try:
        midi_data = pretty_midi.PrettyMIDI(input_midi_file)
    except Exception as e:
        print(f"讀取 MIDI 文件出錯：{e}")
        return default_key

    if midi_data.key_signature_changes:
        # 取第一個 key signature 事件作為代表
        ks = midi_data.key_signature_changes[0]
        # 建立一個映射（這裡只考慮大調的情況）
        mapping = {
            0: "C",
            1: "G",
            2: "D",
            3: "A",
            4: "E",
            5: "B",
            6: "F#",
            7: "C#",
            -1: "F",
            -2: "Bb",
            -3: "Eb",
            -4: "Ab",
            -5: "Db",
            -6: "Gb",
            -7: "Cb"
        }
        key_str = mapping.get(ks.key_number, default_key)
        print(f"從 MIDI 中讀取到的調性為: {key_str}")
        return key_str
    else:
        print(f"MIDI 中未找到 Key Signature 事件，預設使用 {default_key} 調")
        return default_key

def compute_average_velocity(input_midi_file: str) -> int:
    """
    遍歷原始 MIDI 文件中所有音符，計算平均 velocity 作為音量參考值。
    若沒有音符，則返回預設值 90。
    """
    try:
        midi_data = pretty_midi.PrettyMIDI(input_midi_file)
    except Exception as e:
        raise RuntimeError(f"讀取 MIDI 文件出錯: {e}")
    
    velocities = []
    for instrument in midi_data.instruments:
        for note in instrument.notes:
            velocities.append(note.velocity)
    
    if velocities:
        avg_velocity = int(round(sum(velocities) / len(velocities)))
        print(f"計算得到原始 MIDI 平均音量: {avg_velocity}")
        return avg_velocity
    else:
        print("原始 MIDI 沒有檢測到音符，使用預設音量 90")
        return 90


def generate_chord_measures(
    key_str: str,
    mode_str: str,
    progression: list,
    time_sig: tuple,
    tempo: int,
    repeats: int
):
    """
    根據設定生成和弦的 Measure 列表
    
    Args:
        key_str: 例如 "C"
        mode_str: 調式（例如 "Major" 或 "Minor"）
        progression: 和弦進行列表（例如 [2, 5, 1, 6]）
        time_sig: 節拍（例如 (4, 4)）
        tempo: BPM
        repeats: 重複和弦進行的次數
        
    Returns:
        一組 Measure，每個 Measure 代表一小節的和弦
    """
    note_obj = note_from_string(key_str)
    mode_obj = parse_mode(mode_str)
    key_obj = Key(note_obj, mode_obj)
    time_signature = TimeSignature(*time_sig)

    measures = []
    for _ in range(repeats):
        for degree in progression:
            chord = key_obj.relative_key(degree).chord()
            measure = Measure.from_pattern(
                pattern=[chord] * time_signature.numerator,
                time_signature=time_signature
            )
            measures.append(measure)
    return measures


def create_chord_midi_from_measures(measures, tempo: int) -> pretty_midi.PrettyMIDI:
    """
    利用生成的 measures 建立和弦軌道並返回 PrettyMIDI 物件。
    
    此函式使用暫存檔案方式進行 MIDI 輸出與讀取，從而取得 PrettyMIDI 物件。
    """
    chords_track = Track.from_measures(measures)
    song = Song([chords_track])
    
    with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as tmp:
        tmp_filename = tmp.name

    # 將 Song 導出為 MIDI 文件
    song.to_midi(tmp_filename, tempo=tempo)
    
    # 讀取該 MIDI 輸出文件以獲取 PrettyMIDI 對象
    midi_object = pretty_midi.PrettyMIDI(tmp_filename)
    
    os.remove(tmp_filename)
    return midi_object


def apply_volume_to_midi(midi_obj: pretty_midi.PrettyMIDI, volume: int):
    """
    動態調整 MIDI 物件內所有音符的音量（velocity）。
    
    Args:
        midi_obj: 待調整的 PrettyMIDI 物件
        volume: 整數值，建議介於 0 到127 之間
    """
    for instrument in midi_obj.instruments:
        for note in instrument.notes:
            note.velocity = volume


def combine_midis(original_midi_file: str, chord_midi: pretty_midi.PrettyMIDI, output_file: str):
    """
    將原始 MIDI 文件（來自 piano_transcription）與生成的和弦 MIDI 合併，
    並將最終結果寫入 output_file 中。
    """
    try:
        original_midi = pretty_midi.PrettyMIDI(original_midi_file)
    except Exception as e:
        raise RuntimeError(f"讀取原始 MIDI 文件出錯: {e}")

    # 將 chord_midi 中所有樂器的音軌添加到原始 MIDI 中
    for instrument in chord_midi.instruments:
        original_midi.instruments.append(instrument)

    original_midi.write(output_file)
    print(f"合併後的 MIDI 文件已生成：{output_file}")


def main():
    # 原始 MIDI 文件
    input_midi_file = "Twinkle twinkle little star.mid"
    output_file = "combined_output.mid"
    detected_key = get_midi_key(input_midi_file, default_key="C")       # 如果你希望變更預設的和弦key，只需要在調用時指定default_key的值
    mode_str = "Major"     # 這裡可以自由設定，大部分情況下如果是大調，選擇 "Major"
    progression = [2, 5, 1, 6]      # ii-V-I-vi
    time_sig = (4, 4)
    default_tempo = 90

    try:
        tempo, duration = get_midi_info(input_midi_file)
    except Exception as e:
        print(e)
        print("使用預設 BPM 及時長")
        tempo = default_tempo
        duration = 60

    measure_length = (time_sig[0] * 60) / tempo
    total_measures_needed = math.ceil(duration / measure_length)
    repeats = math.ceil(total_measures_needed / len(progression))
    
    # 運用動態獲得的調性 － detected_key
    measures = generate_chord_measures(detected_key, mode_str, progression, time_sig, tempo, repeats)
    
    # 此後流程不變
    chord_midi_object = create_chord_midi_from_measures(measures, tempo)
    desired_volume = compute_average_velocity(input_midi_file)
    apply_volume_to_midi(chord_midi_object, desired_volume)
    combine_midis(input_midi_file, chord_midi_object, output_file)

if __name__ == "__main__":
    main()
