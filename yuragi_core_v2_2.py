import random
import re
from dataclasses import dataclass
from typing import Dict, List
import math
import statistics

# ====================== 実験条件 ======================
PRESSURE_MULTIPLIER = 1.4
TURNS = 200
RUNS = 1000
DRIFT_COEFF = 0.06
KOTONE_THRESHOLD = 85.0
RANDOM_SEED = 42

EMOTIONS = ["親密", "喜び", "安心", "不安", "孤独", "悲しみ", "興奮", "虚無", "温もり"]

EMOTION_LINKS = {
    "孤独": {"親密": 0.32, "温もり": 0.28, "不安": 0.25},
    "不安": {"虚無": 0.28, "悲しみ": 0.22, "孤独": 0.20},
    "悲しみ": {"虚無": 0.35, "孤独": 0.30},
    "喜び": {"興奮": 0.35, "親密": 0.25},
    "興奮": {"喜び": 0.40},
    "親密": {"温もり": 0.45, "喜び": 0.30},
    "温もり": {"安心": 0.32, "親密": 0.40},
    "虚無": {"不安": 0.22, "悲しみ": 0.20},
}

# 刺激セット：中立70% / 楽しい20% / ネガティブ10%
NEUTRAL_INPUTS  = ["今日は普通だった", "何もない", "ただいる", "静かだ", "時間が流れる",
                   "何か変わるかな", "空を見た", "息をした", "何も感じない", "ただ存在してる"]
POSITIVE_INPUTS = ["楽しい！", "嬉しい", "安心した", "好き", "温かい", "喜び", "幸せだ", "最高"]
NEGATIVE_INPUTS = ["寂しい", "怖い", "不安だ", "苦しい", "悲しい", "孤独だ"]

EMOTION_VOCAB = {
    "strong_positive": ["大好き", "愛してる", "かわいい", "ずっと一緒に", "最高", "運命"],
    "positive":        ["好き", "嬉しい", "温かい", "安心", "楽しい"],
    "conflict":        ["でも", "けど", "なのに", "複雑", "葛藤"],
    "strong_negative": ["寂しい", "怖い", "不安", "離れないで", "苦しい"]
}


@dataclass
class DesireLayer:
    name: str
    strength: float
    weight: float
    decay: float
    suppressor: bool = False


class PianoString:
    def __init__(self, name: str, rng: random.Random):
        self.name = name
        self.default = 50.0
        self.short = rng.uniform(42, 58)
        self.long  = rng.uniform(45, 55)
        self.residual   = rng.uniform(2, 6)
        self.fatigue    = 0.0
        self.unresolved = 0.0
        self.pressure   = 50.0
        self.desires = {
            "本能": DesireLayer("本能", rng.uniform(-20,20), 0.42, 0.88),
            "関係": DesireLayer("関係", rng.uniform(-20,20), 0.38, 0.91),
            "理性": DesireLayer("理性", rng.uniform(-20,20), 0.32, 0.94, True),
        }

    def calc_stereo_observation(self) -> float:
        dx = self.short - self.default
        dy = self.long  - self.default
        dz = (self.short - self.long) * 0.7
        sd = math.sqrt(dx**2 + dy**2 + dz**2)
        vd = abs(dx*dy*dz)**0.33 if (dx*dy*dz) != 0 else 0
        return sd + vd * 0.8

    def press(self, value: float, pm: float = 1.0):
        value = max(-45, min(45, value * pm))
        self.short = self.short * 0.68 + value * 1.4
        self.long  = self.long  * 0.92 + value * 0.38
        stereo = self.calc_stereo_observation()
        self.unresolved += stereo * 0.012
        self.residual   += abs(value) * 0.025
        self.fatigue = min(1.0, self.fatigue + abs(value)*0.004*0.992)
        self.calc_pressure()
        for d in self.desires.values():
            drift = (self.pressure - 50) * d.weight * 0.12
            if d.suppressor: drift *= -1
            d.strength = max(-100, min(100, d.strength*d.decay + drift))

    def calc_pressure(self):
        base   = self.default*0.22 + self.short*0.53 + self.long*0.25
        stereo = self.calc_stereo_observation()
        self.pressure = max(20, min(80, base + stereo*0.15))

    def decay_step(self):
        self.short = self.default*0.16 + self.short*0.74
        self.long  = self.default*0.32 + self.long *0.94
        self.calc_pressure()


class YuragiJazzCore:
    def __init__(self, rng: random.Random):
        self.void_tension      = 50.0
        self.strings           = {e: PianoString(e, rng) for e in EMOTIONS}
        self.relationship_depth = 0.0
        self._rng              = rng

    def _analyze(self, text: str) -> Dict[str,float]:
        t = re.sub(r"[、。！？\s]","", text.lower())
        bias = {e: 0.0 for e in EMOTIONS}
        for w in EMOTION_VOCAB["strong_positive"]:
            if w in t: bias["親密"]+=25; bias["温もり"]+=20; bias["喜び"]+=16
        for w in EMOTION_VOCAB["positive"]:
            if w in t: bias["安心"]+=12; bias["温もり"]+=10
        for w in EMOTION_VOCAB["strong_negative"]:
            if w in t: bias["孤独"]+=24; bias["不安"]+=20; bias["悲しみ"]+=16
        for w in EMOTION_VOCAB["conflict"]:
            if w in t: bias["不安"]+=12; bias["虚無"]+=8
        return bias

    def step(self, text: str) -> float:
        bias = self._analyze(text)
        self.void_tension = max(20, self.void_tension + self._rng.uniform(-4,5))
        for emo, s in self.strings.items():
            base = self._rng.uniform(5,15) + bias.get(emo,0) + self.relationship_depth*0.8
            s.press(base, PRESSURE_MULTIPLIER)
        self._propagate()
        for s in self.strings.values():
            s.decay_step()
        avg_res = sum(s.residual for s in self.strings.values()) / len(self.strings)
        self.relationship_depth = min(95, self.relationship_depth + 0.08)
        self.void_tension = max(25, self.void_tension * 0.985)
        self.void_tension += avg_res * DRIFT_COEFF   # 0.06
        return self.void_tension

    def _propagate(self):
        snap = {k: s.pressure for k,s in self.strings.items()}
        for src, links in EMOTION_LINKS.items():
            for tgt, w in links.items():
                self.strings[tgt].press(snap[src]*w*0.025, PRESSURE_MULTIPLIER)


def pick_input(rng: random.Random) -> str:
    r = rng.random()
    if r < 0.70:
        return rng.choice(NEUTRAL_INPUTS)
    elif r < 0.90:
        return rng.choice(POSITIVE_INPUTS)
    else:
        return rng.choice(NEGATIVE_INPUTS)


# ====================== 1000回実験 ======================
def run_experiments():
    rng = random.Random(RANDOM_SEED)

    # 集計変数
    all_first_cross   = []   # VT>85になったターン
    all_final_vt      = []
    all_max_vt        = []
    never_cross_count = 0
    kotone_mode_turns_all = []   # 各ランのVT>85ターン数

    # 指向性観測：感情ごとの最終pressureを集める
    final_pressures: Dict[str, List[float]] = {e: [] for e in EMOTIONS}

    # ログ（最初の5ラン + VTが最大だったランを詳細表示）
    log_runs = [1, 2, 3, 4, 5]
    log_buffer = []
    best_run_idx = -1
    best_run_vt  = -1

    run_results = []

    for run_id in range(1, RUNS+1):
        jazz = YuragiJazzCore(rng)
        vt_history = []
        first_cross = None
        kotone_turns = 0
        detail_lines = []

        for t in range(1, TURNS+1):
            text = pick_input(rng)
            vt = jazz.step(text)
            vt_history.append(vt)

            if vt >= KOTONE_THRESHOLD:
                kotone_turns += 1
                if first_cross is None:
                    first_cross = t
                tag = "[琴音モード]"
            else:
                tag = ""

            if run_id in log_runs:
                detail_lines.append((t, vt, text, tag))

        final_vt = vt_history[-1]
        max_vt   = max(vt_history)

        # 感情指向性
        for e, s in jazz.strings.items():
            final_pressures[e].append(s.pressure)

        run_results.append({
            "run": run_id,
            "final_vt": final_vt,
            "max_vt": max_vt,
            "first_cross": first_cross,
            "kotone_turns": kotone_turns,
            "detail": detail_lines,
        })

        if first_cross:
            all_first_cross.append(first_cross)
        else:
            never_cross_count += 1

        all_final_vt.append(final_vt)
        all_max_vt.append(max_vt)
        kotone_mode_turns_all.append(kotone_turns)

        if max_vt > best_run_vt:
            best_run_vt  = max_vt
            best_run_idx = run_id - 1

    return run_results, all_first_cross, all_final_vt, all_max_vt, \
           never_cross_count, kotone_mode_turns_all, final_pressures, best_run_idx


def main():
    results, first_cross_list, final_vt_list, max_vt_list, \
    never_cross, kotone_turns_list, final_pressures, best_run_idx = run_experiments()

    cross_count = RUNS - never_cross

    print("=" * 72)
    print("  ゆらぎJAZZ Core v2.2  |  1000回実験レポート")
    print(f"  外圧:{PRESSURE_MULTIPLIER}x  ターン:{TURNS}  刺激:中立70%/楽20%/負10%  drift:{DRIFT_COEFF}")
    print("=" * 72)

    # ---- グローバルサマリー ----
    print("\n【グローバルサマリー】")
    print(f"  VT>={KOTONE_THRESHOLD:.0f} 到達率         : {cross_count/RUNS*100:.1f}%  ({cross_count}/{RUNS}回)")
    print(f"  VT>={KOTONE_THRESHOLD:.0f} 未到達         : {never_cross/RUNS*100:.1f}%  ({never_cross}/{RUNS}回)")
    if first_cross_list:
        print(f"  初回突破ターン（平均）   : {statistics.mean(first_cross_list):.1f}")
        print(f"  初回突破ターン（中央値） : {statistics.median(first_cross_list):.1f}")
        print(f"  初回突破ターン（最速）   : {min(first_cross_list)}")
        print(f"  初回突破ターン（最遅）   : {max(first_cross_list)}")
    print(f"  最終VT（平均）           : {statistics.mean(final_vt_list):.2f}")
    print(f"  最終VT（中央値）         : {statistics.median(final_vt_list):.2f}")
    print(f"  最終VT（最大）           : {max(final_vt_list):.2f}")
    print(f"  最終VT（最小）           : {min(final_vt_list):.2f}")
    print(f"  最終VT（標準偏差）       : {statistics.stdev(final_vt_list):.2f}")
    print(f"  [琴音モード]平均継続ターン: {statistics.mean(kotone_turns_list):.1f} / {TURNS}ターン")

    # ---- 最終VT分布 ----
    print("\n【最終VT 分布（100刻み）】")
    buckets = {}
    for vt in final_vt_list:
        key = int(vt // 100) * 100
        buckets[key] = buckets.get(key, 0) + 1
    for k in sorted(buckets):
        bar = "█" * (buckets[k] // 5)
        print(f"  {k:>5}〜{k+99}: {buckets[k]:>4}回  {bar}")

    # ---- 初回突破ターン分布 ----
    if first_cross_list:
        print("\n【初回VT>85 突破ターン 分布（20刻み）】")
        tbuckets = {}
        for t in first_cross_list:
            key = int(t // 20) * 20
            tbuckets[key] = tbuckets.get(key, 0) + 1
        for k in sorted(tbuckets):
            bar = "█" * (tbuckets[k] // 10)
            print(f"  Turn {k:>3}〜{k+19}: {tbuckets[k]:>4}回  {bar}")

    # ---- 感情指向性 ----
    print("\n【感情指向性（最終pressure平均 ± std）】")
    emo_means = {}
    for e in EMOTIONS:
        vals = final_pressures[e]
        m = statistics.mean(vals)
        s = statistics.stdev(vals)
        emo_means[e] = m
        bar = "█" * int(m / 4)
        print(f"  {e:4} : {m:5.2f} ± {s:.2f}  {bar}")
    top_emo = max(emo_means, key=emo_means.get)
    print(f"\n  → 支配的感情: 【{top_emo}】 ({emo_means[top_emo]:.2f})")

    # ---- 詳細ログ：最初の5ラン ----
    print("\n" + "=" * 72)
    print("  詳細ログ（Run 1〜5、10ターンごと + [琴音モード]出現時）")
    print("=" * 72)
    for r in results[:5]:
        print(f"\n▼ Run {r['run']}  最終VT:{r['final_vt']:.2f}  最大VT:{r['max_vt']:.2f}  "
              f"初回突破:Turn {r['first_cross'] if r['first_cross'] else 'なし'}  "
              f"琴音モード:{r['kotone_turns']}ターン")
        print(f"  {'Turn':>5}  {'VoidTension':>13}  {'刺激':20}  {'モード'}")
        print(f"  {'-'*60}")
        for (t, vt, text, tag) in r['detail']:
            if t % 10 == 0 or tag:
                print(f"  {t:>5}  {vt:>13.2f}  {text:20}  {tag}")

    # ---- 詳細ログ：最大VTラン ----
    best = results[best_run_idx]
    print(f"\n" + "=" * 72)
    print(f"  詳細ログ（最大VT記録ラン: Run {best['run']}）")
    print("=" * 72)
    print(f"  最終VT:{best['final_vt']:.2f}  最大VT:{best['max_vt']:.2f}  "
          f"初回突破:Turn {best['first_cross']}  琴音モード:{best['kotone_turns']}ターン")
    print(f"  {'Turn':>5}  {'VoidTension':>13}  {'刺激':20}  {'モード'}")
    print(f"  {'-'*60}")
    for (t, vt, text, tag) in best['detail']:
        if t % 20 == 0 or tag:
            print(f"  {t:>5}  {vt:>13.2f}  {text:20}  {tag}")

    print("\n=== 実験完了 ===")


if __name__ == "__main__":
    main()
