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
    """
    try:
        midi_data = pretty_midi.PrettyMIDI(input_midi_file)
    except Exception as e:
        print(f"讀取 MIDI 文件出錯：{e}")
        return default_key

    if midi_data.key_signature_changes:
        ks = midi_data.key_signature_changes[0]  # 使用第一個 key signature 事件
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
    根據設定生成和弦的 Measure 列表。
    每個 Measure 代表一小節的和弦，內部每個和弦的時值由 time_sig 決定。
    當 progression 中出現 0 時，表示此小節為停頓，生成 dummy 和弦（以 -1 表示）。
    """
    note_obj = note_from_string(key_str)
    mode_obj = parse_mode(mode_str)
    key_obj = Key(note_obj, mode_obj)
    time_signature = TimeSignature(*time_sig)

    measures = []
    for _ in range(repeats):
        for degree in progression:
            if degree == 0:
                # 使用 [0] 表示停頓，0 為合法值
                chord = [0]
            else:
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
    此函式利用暫存檔輸出與讀取 MIDI 文件。
    """
    chords_track = Track.from_measures(measures)
    song = Song([chords_track])
    
    with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as tmp:
        tmp_filename = tmp.name

    song.to_midi(tmp_filename, tempo=tempo)
    midi_object = pretty_midi.PrettyMIDI(tmp_filename)
    os.remove(tmp_filename)
    return midi_object


def mark_dummy_notes(midi_obj: pretty_midi.PrettyMIDI):
    for instrument in midi_obj.instruments:
        if instrument.is_drum:
            continue
        for note in instrument.notes:
            if note.pitch == 0:
                note._dummy = True


def apply_volume_to_midi(midi_obj: pretty_midi.PrettyMIDI, volume: int):
    """
    調整所有音符的 velocity 為指定值，dummy note 保持原狀。
    """
    for instrument in midi_obj.instruments:
        for note in instrument.notes:
            if hasattr(note, "_dummy") and note._dummy:
                continue
            note.velocity = volume


def transpose_midi(midi_obj: pretty_midi.PrettyMIDI, semitones: int):
    """
    將所有非打擊樂器的音符轉調指定的半音數，跳過 dummy note。
    """
    for instrument in midi_obj.instruments:
        if instrument.is_drum:
            continue
        for note in instrument.notes:
            if hasattr(note, "_dummy") and note._dummy:
                continue
            new_pitch = note.pitch + semitones
            note.pitch = max(0, min(new_pitch, 127))


def combine_midis(original_midi_file: str, chord_midi: pretty_midi.PrettyMIDI, output_file: str):
    """
    合併原始 MIDI 文件與生成的和弦 MIDI，寫入 output_file 中。
    """
    try:
        original_midi = pretty_midi.PrettyMIDI(original_midi_file)
    except Exception as e:
        raise RuntimeError(f"讀取原始 MIDI 文件出錯: {e}")

    for instrument in chord_midi.instruments:
        original_midi.instruments.append(instrument)
    original_midi.write(output_file)
    print(f"合併後的 MIDI 文件已生成：{output_file}")


def get_fixed_beat_duration(time_sig: tuple) -> float:
    """
    根據時間簽名返回固定的每拍持續時間（秒）。
    例如：
      4/4 拍：返回 0.5 秒/拍
      3/4 拍：返回 0.66 秒/拍
      2/4 拍：返回 1.0 秒/拍
    若有其它時間簽名，可根據需要添加對應邏輯，這裡默認返回 0.5 秒。
    """
    numerator, denominator = time_sig
    if time_sig == (4, 4):
        return 0.5
    elif time_sig == (3, 4):
        return 0.66
    elif time_sig == (2, 4):
        return 1.0
    else:
        return 0.5  # 默認值，可根據需要調整


def adjust_chord_duration_fixed(midi_obj: pretty_midi.PrettyMIDI, beat_duration: float):
    """
    將和弦 MIDI 中所有非打擊樂器的音符持續時間固定為 beat_duration（秒）。
    """
    for instrument in midi_obj.instruments:
        if not instrument.is_drum:
            for note in instrument.notes:
                note.end = note.start + beat_duration


def connect_chord_notes_grouped(midi_obj: pretty_midi.PrettyMIDI, tolerance: float = 0.001):
    """
    根據起始時間將音符分組，同一組的音符不進行調整。
    對於相鄰組別，無條件將后一組的所有音符的起始時間設置為前一組中最晚的結束時間，
    並保留原有的持續時間。
    """
    for instrument in midi_obj.instruments:
        if instrument.is_drum:
            continue
        instrument.notes.sort(key=lambda note: note.start)
        groups = []
        current_group = [instrument.notes[0]]
        for note in instrument.notes[1:]:
            if abs(note.start - current_group[0].start) <= tolerance:
                current_group.append(note)
            else:
                groups.append(current_group)
                current_group = [note]
        groups.append(current_group)
        for i in range(1, len(groups)):
            prev_group_end = max(n.end for n in groups[i - 1])
            for note in groups[i]:
                duration = note.end - note.start
                note.start = prev_group_end
                note.end = note.start + duration

def remove_dummy_notes(midi_obj: pretty_midi.PrettyMIDI):
    """
    從 MIDI 物件中移除所有被標記爲 dummy 的音符，
    這樣 dummy note 就不會出現在最終輸出的 MIDI 文件或樂譜中。
    """
    for instrument in midi_obj.instruments:
        instrument.notes = [note for note in instrument.notes if not (hasattr(note, '_dummy') and note._dummy)]

def main():
    # 原始 MIDI 文件
    input_midi_file = "Twinkle twinkle little star.mid"
    output_file = "combined_output.mid"
    detected_key = get_midi_key(input_midi_file, default_key="C")
    mode_str = "Major"          # 使用大調
    # 進行中 0 表示停頓，例如 (2, 5, 0, 1) 表示 ii-V-停頓-I
    progression = [2, 5, 0, 1]
    time_sig = (4, 4)           # 設定節拍
    default_tempo = 90  # 此 tempo 僅用於生成 MIDI 時的標記，不影響和弦時長的固定計算

    try:
        tempo, duration = get_midi_info(input_midi_file)
    except Exception as e:
        print(e)
        print("使用預設 BPM 及時長")
        tempo = default_tempo
        duration = 60

    beat_duration = get_fixed_beat_duration(time_sig)
    measure_length = time_sig[0] * beat_duration  # 例如在 4/4 拍中：4 * 0.5 = 2.0 秒/小節
    total_measures_needed = math.ceil(duration / measure_length)
    repeats = math.ceil(total_measures_needed / len(progression))

    # 生成和弦 measures（保留原進行順序，0 表示停頓）
    measures = generate_chord_measures(detected_key, mode_str, progression, time_sig, tempo, repeats)

    # 生成和弦 MIDI 物件
    chord_midi_object = create_chord_midi_from_measures(measures, tempo)

    # 標記 dummy note（停頓）— 其 pitch 為 0 的 note
    mark_dummy_notes(chord_midi_object)

    # 將和弦音量調整為與原始 MIDI 平均音量相同，
    # dummy note 不作調整
    desired_volume = compute_average_velocity(input_midi_file)
    apply_volume_to_midi(chord_midi_object, desired_volume)

    # 固定每個和弦持續時間為計算得到的 beat_duration（不依賴 BPM）
    adjust_chord_duration_fixed(chord_midi_object, beat_duration)

    # 將各和弦無縫連接，dummy note 保持在原位置
    connect_chord_notes_grouped(chord_midi_object)

    # 將和弦整體轉調（例如下降兩個八度，-24 半音）；dummy note 保持不變
    transpose_midi(chord_midi_object, -24)

    # 移除dummy note，這樣它們不會顯示在樂譜中
    remove_dummy_notes(chord_midi_object)

    # 合併原始 MIDI 與和弦 MIDI，生成最終文件
    combine_midis(input_midi_file, chord_midi_object, output_file)


if __name__ == "__main__":
    main()