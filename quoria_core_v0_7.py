import random
import math
from dataclasses import dataclass
from typing import Dict, List
import statistics

RUNS = 100
TURNS = 500
SEED = 42

# 固定伝播用リンク（空洞コアと同じ構造をクオリアコアに移植）
FIXED_LINKS = {
    "親密": {"安心": 0.35, "喜び": 0.25},
    "喜び": {"未知": 0.30, "親密": 0.20},
    "不安": {"親密": 0.25, "安心": 0.20},
    "安心": {"喜び": 0.28},
    "未知": {"喜び": 0.32, "不安": 0.18},
}

@dataclass
class Bubble:
    strength: float
    correlation: float
    linkage: float
    emotion_type: str

class QuoriaVariant:
    def __init__(self, rng, pressure=1.6, drift=0.045,
                 fixed_propagation=False, threshold_reset=True):
        self.repulsion = 0.0
        self.void_tension = 50.0
        self.residual = 0.0
        self.pressure = pressure
        self.drift = drift
        self.fixed_propagation = fixed_propagation
        self.threshold_reset = threshold_reset
        self._rng = rng

        self.emotions = {
            "親密": {"short": 48.0, "long": 52.0},
            "喜び": {"short": 45.0, "long": 55.0},
            "不安": {"short": 52.0, "long": 48.0},
            "安心": {"short": 50.0, "long": 50.0},
            "未知": {"short": 47.0, "long": 53.0},
        }
        self.desires      = {"本能":55.0,"関係":60.0,"成長":52.0,"未知":58.0,"創造":50.0}
        self.rationality  = {"抑制":48.0,"調整":52.0,"貫通":55.0,"省察":50.0,"均衡":53.0}
        self.personality  = {"内向性":45.0,"冒険性":55.0,"共感性":60.0,"柔軟性":50.0,"安定志向":52.0}
        self.environment  = {"刺激量":48.0,"文化適合":53.0,"空間快適":50.0}

    def _emit_bubbles(self):
        self.repulsion += self._rng.uniform(0.8, 2.5) * self.pressure
        self.void_tension = max(20, min(80, self.void_tension + self._rng.uniform(-3, 3)))

        bubbles = []
        if self.repulsion > 18.0:
            num = self._rng.randint(2, 5)
            for _ in range(num):
                if self.fixed_propagation:
                    # 固定：リンクの重みに従って対象感情を選ぶ
                    src = self._rng.choice(list(self.emotions.keys()))
                    targets = FIXED_LINKS.get(src, {})
                    if targets:
                        emo = max(targets, key=targets.get)
                    else:
                        emo = src
                else:
                    # ランダム放出
                    emo = self._rng.choice(list(self.emotions.keys()))

                b = Bubble(
                    strength=self._rng.uniform(0.6, 1.4) * self.pressure,
                    correlation=self._rng.uniform(0.4, 0.9),
                    linkage=self._rng.uniform(0.5, 1.1),
                    emotion_type=emo
                )
                bubbles.append(b)

            if self.threshold_reset:
                self.repulsion = 0.0   # 閾値リセットあり
            # リセットなしの場合はrepulsionが累積し続ける

        return bubbles

    def _propagate(self, bubble):
        if bubble.emotion_type in self.emotions:
            self.emotions[bubble.emotion_type]["short"] += bubble.strength * 1.8
            self.emotions[bubble.emotion_type]["long"]  += bubble.strength * 0.9

        for d in self.desires:     self.desires[d]     += bubble.correlation * 0.6
        for r in self.rationality: self.rationality[r] += bubble.linkage * 0.4
        for p in self.personality: self.personality[p] += bubble.strength * 0.3
        for e in self.environment: self.environment[e] += bubble.correlation * 0.35

        self.residual += abs(bubble.strength) * 0.025

        for emo in self.emotions:
            self.emotions[emo]["short"] *= 0.985
            self.emotions[emo]["long"]  *= 0.985
        for k in self.desires:     self.desires[k]     *= 0.985
        for k in self.rationality: self.rationality[k] *= 0.985
        for k in self.personality: self.personality[k] *= 0.985
        for k in self.environment: self.environment[k] *= 0.985

    def step(self):
        self.repulsion += self._rng.uniform(1, 4)
        bubbles = self._emit_bubbles()
        for b in bubbles:
            self._propagate(b)
        self.void_tension += self.residual * self.drift
        return self.void_tension

    def top_emotion(self):
        gaps = {k: abs(v["short"]-v["long"]) for k,v in self.emotions.items()}
        return max(gaps, key=gaps.get)


# ====================== 実験設定 ======================
configs = [
    # (名前, pressure, drift, fixed_prop, threshold_reset)
    ("①ベースライン（ランダム/リセットあり/drift0.045）", 1.6, 0.045, False, True),
    ("②固定伝播（ランダム→固定）",                       1.6, 0.045, True,  True),
    ("③閾値リセットOFF（蓄積型）",                       1.6, 0.045, False, False),
    ("④drift弱（0.01）",                                1.6, 0.010, False, True),
    ("⑤drift強（0.10）",                                1.6, 0.100, False, True),
    ("⑥固定+リセットOFF（複合）",                        1.6, 0.045, True,  False),
]

print("=" * 70)
print("  クオリアコア 要因切り分け実験")
print(f"  {RUNS}回 × {TURNS}ターン | seed={SEED}")
print("=" * 70)

all_results = {}

for cfg_name, pressure, drift, fixed_prop, thr_reset in configs:
    rng = random.Random(SEED)
    final_vts  = []
    final_res  = []
    top_emos   = []
    vt_at = {100:[], 300:[], 500:[]}

    for run in range(RUNS):
        core = QuoriaVariant(rng, pressure, drift, fixed_prop, thr_reset)
        for t in range(1, TURNS+1):
            vt = core.step()
            if t in vt_at:
                vt_at[t].append(vt)
        final_vts.append(core.void_tension)
        final_res.append(core.residual)
        top_emos.append(core.top_emotion())

    emo_counts = {}
    for e in top_emos:
        emo_counts[e] = emo_counts.get(e, 0) + 1
    top1 = max(emo_counts, key=emo_counts.get)
    spread = max(emo_counts.values()) - min(emo_counts.values())
    at_cap = sum(1 for v in final_vts if v >= 80)

    all_results[cfg_name] = {
        "mean_vt": statistics.mean(final_vts),
        "max_vt":  max(final_vts),
        "std_vt":  statistics.stdev(final_vts),
        "mean_res": statistics.mean(final_res),
        "top_emo": top1,
        "emo_spread": spread,
        "at_cap": at_cap,
        "vt_at": {t: round(statistics.mean(v),2) for t,v in vt_at.items()},
        "emo_counts": emo_counts,
    }

# ====================== 結果出力 ======================
for name, r in all_results.items():
    print(f"\n▼ {name}")
    print(f"  VT最終: 平均{r['mean_vt']:7.2f}  最大{r['max_vt']:7.2f}  標準偏差{r['std_vt']:.2f}")
    print(f"  残渣最終平均: {r['mean_res']:.3f}")
    print(f"  VT推移: T100={r['vt_at'][100]}  T300={r['vt_at'][300]}  T500={r['vt_at'][500]}")
    print(f"  天井到達(≥80): {r['at_cap']}/100回")
    print(f"  支配感情: 【{r['top_emo']}】  感情間スプレッド: {r['emo_spread']}")
    counts_str = "  ".join(f"{e}:{c}回" for e,c in sorted(r['emo_counts'].items(), key=lambda x:-x[1]))
    print(f"  感情分布: {counts_str}")

# ====================== 比較サマリー ======================
print("\n" + "=" * 70)
print("  要因別 比較サマリー")
print("=" * 70)
print(f"\n  {'設定':35} | {'VT平均':>8} | {'天井':>6} | {'支配感情':6} | {'指向性強さ'}")
print(f"  {'-'*75}")
for name, r in all_results.items():
    directionality = "強" if r['emo_spread'] > 15 else "中" if r['emo_spread'] > 8 else "弱"
    print(f"  {name:35} | {r['mean_vt']:>8.2f} | {r['at_cap']:>5}回 | {r['top_emo']:6} | {directionality}")

print("""
【読み方】
  VT平均     : 高いほど蓄積が強い
  天井到達   : VT≥80に達した回数（100回中）
  指向性強さ : 感情分布のスプレッド（大きいほど特定感情に偏る）
""")
