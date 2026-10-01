/**
 * BeatGrid — P9.1. A beat grid derived from the audio, not from a number in the
 * graph.
 *
 * WHY THIS EXISTS. `showcase-v1` has carried a `bpm` field and beat maths on both
 * ends since P3: `beatFrames = (60 / bpm) * fps`, `beat_distance_frames`,
 * `resolveScenes(beat_snap)`. The tempo itself was never measured against
 * anything. Meanwhile `studio/public/audio/bgm_beats.json` — 208 beats detected
 * from the real track, `source: mixtrack_Digital_Clouds.mp3` — is committed,
 * describes itself as "for the renderer", and had ZERO readers.
 *
 * The two do not agree, and the gap is not small:
 *
 *   graph declares 126 bpm   |  track measures 129.00 bpm
 *   126/129.00 = 0.9767, and it compounds: 1 beat 11.8 ms, 8 beats 94.4 ms,
 *   32 beats 377.4 ms, 208 beats 2453.2 ms — nearly two and a half seconds of
 *   drift by the end of the analysed track. Anything bound to the grid is bound
 *   to the wrong tempo, and the error is a function of how far in you look, so
 *   it passes every short test.
 *
 * The 126 is not an arbitrary typo. The README explains it: `bgm_synth_126.m4a`
 * is the offline synthetic fallback, the real Mixkit track replaced it, and
 * `README.md:35` warns that after swapping the BGM you must update the graph's
 * bpm. That warning is what got skipped, because nothing could fail on it. So
 * this module's job is not only to compute a grid — it is to make the declared
 * tempo something that can DISAGREE visibly with the measured one.
 *
 * TWO THINGS THIS DELIBERATELY DOES NOT DO.
 *
 * 1. It does not infer accents from beat indices. The temptation is `i % 4` for
 *    "the downbeat", because 4/4 is the usual metre. Measured against this
 *    track that is false: a permutation test over the detected bass values finds
 *    NO index modulus that predicts loudness — observed spread 0.032 at mod 4
 *    against a shuffled-null 95th percentile of 0.070. The 12 loudest beats sit
 *    at indices 2, 20, 22, 56, 58, 82, 84, 89, 96, 98, 114, 115, covering all
 *    four residues mod 4, with gaps of 1 to 34 beats. Accent comes from the
 *    analysis or it does not exist; `accent` below is a selection of measured
 *    beats and is deliberately not a function of position.
 *
 * 2. It does not use the file's self-reported `bpm`/`beat_interval`. Those are a
 *    summary the generator wrote, and they disagree with the file's own beats:
 *    0.4644s implies 129.20 bpm while a least-squares fit of the same 208 times
 *    gives 129.00 bpm. That is 150 ms across the track, which is 9 frames at
 *    60fps — enough to matter and small enough to pass review. So the fit is the
 *    authority here and the declared values are only ever checked against it.
 *
 * FRAME QUANTISATION, and the limit it runs into. Boundaries are emitted in whole
 * frames so that the four levels tile the timeline exactly: adjacent bar
 * boundaries differ by exactly one bar, with no gap and no overlap, by
 * construction rather than by rounding luck. The cost is that a frame grid can
 * only represent tempos of the form 60*fps/n, so at 60fps one beat is ~27.9
 * frames and the representable grid is 28 frames = 128.571 bpm — a 0.33% tempo
 * error, worth ~2.7 frames over a 801-frame film. That residual is intrinsic to
 * integer frames, not a defect here, so it is REPORTED (`representedBpm`,
 * `tempoErrorPct`, `driftMsAtHorizon`) rather than hidden. Read those before
 * trusting a grid: a tempo error of a third of a percent is invisible in the
 * first bar and visible by the last.
 *
 * Zero react, zero remotion, zero imports. A grid is arithmetic over numbers that
 * came out of an audio file; if reaching it required a renderer, the fit could
 * not be checked without rendering a frame to ask it, which is how the declared
 * bpm stayed wrong for this long.
 */

export type BeatObservation = {
  /** seconds from the start of the track */
  t: number;
  /** low-band energy at this beat, 0..1 as the analyser emitted it */
  bass?: number;
};

/** The shape of `bgm_beats.json`. Only `beats` is required. */
export type BeatAnalysis = {
  bpm?: number;
  beat_interval?: number;
  source?: string;
  beats: BeatObservation[];
};

export type BpmFit = {
  /** 60 / interval */
  bpm: number;
  /** seconds between beats */
  interval: number;
  /** seconds; fitted t at beat index 0 */
  offset: number;
  /** root-mean-square residual, milliseconds */
  rmsMs: number;
  /** largest absolute residual, milliseconds */
  maxMs: number;
  /** beats used */
  count: number;
};

/**
 * Least-squares fit of `t_i = offset + i * interval` over the detected beats.
 *
 * OLS rather than "the interval the file claims" and rather than
 * `mean(diff(t))`, for a reason that is measurable on this very file: the mean of
 * successive differences is dragged by the first and last detections, whereas
 * OLS uses every beat and yields a residual RMS of 7.9 ms against 44.1 ms for the
 * file's own declared interval. A grid built on the declared interval drifts
 * monotonically — residual means of +29 ms over the first quarter and +141 ms
 * over the last — which is exactly the shape of a tempo error nobody notices.
 */
export const fitBpm = (beats: readonly BeatObservation[]): BpmFit => {
  const n = beats.length;
  if (n < 2) {
    throw new Error(`fitBpm needs at least 2 beats, got ${n}`);
  }
  let sumT = 0;
  for (const b of beats) sumT += b.t;
  const meanT = sumT / n;
  const meanX = (n - 1) / 2;
  let num = 0;
  let den = 0;
  for (let i = 0; i < n; i += 1) {
    const dx = i - meanX;
    num += dx * (beats[i].t - meanT);
    den += dx * dx;
  }
  if (den === 0) {
    throw new Error('fitBpm needs distinct beat indices');
  }
  const interval = num / den;
  if (!(interval > 0)) {
    throw new Error(`fitBpm got a non-positive interval (${interval}s); the beat times are not increasing`);
  }
  const offset = meanT - interval * meanX;
  let sumSq = 0;
  let maxAbs = 0;
  for (let i = 0; i < n; i += 1) {
    const r = beats[i].t - (offset + interval * i);
    sumSq += r * r;
    const a = Math.abs(r);
    if (a > maxAbs) maxAbs = a;
  }
  return {
    bpm: 60 / interval,
    interval,
    offset,
    rmsMs: Math.sqrt(sumSq / n) * 1000,
    maxMs: maxAbs * 1000,
    count: n,
  };
};

/** Fraction of beats treated as accented. 5% of this track is 11 of 208. */
export const ACCENT_SHARE = 0.05;

export type GridSpec = {
  /** the tempo to build the grid at — the graph's declared value, deliberately */
  bpm: number;
  fps: number;
};

export type GridOptions = {
  /** how far the grid runs, in frames. Defaults to the analysed track's length. */
  horizonFrames?: number;
};

export type BeatGrid = {
  /** frame boundaries, ascending, starting at 0 */
  quarterBeat: number[];
  halfBeat: number[];
  beat: number[];
  bar: number[];
  /**
   * Beat INDICES whose measured `bass` is in the top ACCENT_SHARE of beats.
   * Indices, not frames, because the caller will be binding a beat ordinal (which
   * is also what the accent MEANS musically). Not derivable from the index —
   * see the note at the top of this file.
   */
  accent: number[];
  framesPerQuarterBeat: number;
  framesPerHalfBeat: number;
  framesPerBeat: number;
  framesPerBar: number;
  /** the tempo an integer-frame grid can actually play */
  representedBpm: number;
  /** (represented - declared) / declared, percent */
  tempoErrorPct: number;
  /** signed grid-minus-ideal offset at the last boundary, milliseconds */
  driftMsAtHorizon: number;
  /**
   * The same drift in BEATS, which is the only horizon-independent way to state
   * it. Milliseconds grow with the horizon by construction, so a millisecond
   * tolerance is really a length tolerance wearing a disguise; a beat count says
   * "the grid is still pointing at the same beat it started on".
   */
  driftBeatsAtHorizon: number;
};

/**
 * Build the grid.
 *
 * The four levels are quantised from the QUARTER beat, not the bar, and the
 * quantisation is to a whole number of quarter-beats. Two consequences, both
 * wanted: every level is an exact integer multiple of the one below it, so no
 * boundary can ever be one frame off its neighbour; and the ideal bar is the only
 * place a rounding decision could desynchronise the levels, which is why it is
 * not the unit of construction.
 *
 * The alternative — quantise each level independently — looks equivalent and is
 * not: at 60fps and 129 bpm the ideal beat is 27.907 frames, which rounds to 28,
 * but the ideal half-beat is 13.953, which rounds to 14, and 28 is not 2x14 only
 * by luck. Whenever the two roundings disagree the bar stops lining up with its
 * own beats, and the symptom is a boundary one frame early that nobody can see.
 */
export const grid = (spec: GridSpec, analysis: BeatAnalysis, options: GridOptions = {}): BeatGrid => {
  const {bpm, fps} = spec;
  if (!(bpm > 0)) throw new Error(`grid needs a positive bpm, got ${bpm}`);
  if (!(fps > 0)) throw new Error(`grid needs a positive fps, got ${fps}`);
  const beats = analysis.beats;
  if (!beats.length) throw new Error('grid needs at least one analysed beat');

  const idealQuarter = (60 / bpm) * fps / 4;
  const q = Math.max(1, Math.round(idealQuarter));
  const half = q * 2;
  const beat = q * 4;
  const bar = q * 16;

  const analysedSeconds = beats[beats.length - 1].t - beats[0].t;
  const horizon = options.horizonFrames ?? Math.max(1, Math.ceil(analysedSeconds * fps));

  const boundaries = (step: number): number[] => {
    const out: number[] = [];
    for (let f = 0; f <= horizon; f += step) out.push(f);
    return out;
  };

  const bass = beats.map((b) => (typeof b.bass === 'number' ? b.bass : 0));
  const take = Math.max(1, Math.ceil(bass.length * ACCENT_SHARE));
  const accent = bass
    .map((v, i) => ({v, i}))
    .sort((a, b) => b.v - a.v || a.i - b.i)
    .slice(0, take)
    .map((x) => x.i)
    .sort((a, b) => a - b);

  const representedBpm = (60 * fps) / beat;
  // The ideal position of the last boundary, against where the grid actually puts
  // it. This is the number that says whether a grid can be trusted this far out.
  const lastBoundary = horizon - (horizon % beat);
  const driftFrames = lastBoundary - (lastBoundary / beat) * ((60 / bpm) * fps);

  return {
    quarterBeat: boundaries(q),
    halfBeat: boundaries(half),
    beat: boundaries(beat),
    bar: boundaries(bar),
    accent,
    framesPerQuarterBeat: q,
    framesPerHalfBeat: half,
    framesPerBeat: beat,
    framesPerBar: bar,
    representedBpm,
    tempoErrorPct: ((representedBpm - bpm) / bpm) * 100,
    driftMsAtHorizon: (driftFrames / fps) * 1000,
    driftBeatsAtHorizon: driftFrames / beat,
  };
};

/**
 * How far a declared tempo is from the measured one, in bpm.
 *
 * Signed, because "3 bpm fast" and "3 bpm slow" are different mistakes and a
 * single absolute number cannot tell them apart in a report.
 */
export const bpmDisagreement = (declared: number, fit: BpmFit): number => declared - fit.bpm;

/**
 * Whether a grid's declared tempo can be trusted for the analysed track.
 *
 * Two separate questions, deliberately not merged: is the DECLARATION right
 * (a data problem, and the one that made this module necessary), and can an
 * integer frame grid REPRESENT that tempo over the horizon (a limit of frames,
 * which no amount of correct data removes).
 */
/**
 * Whether a grid's declared tempo can be trusted for the analysed track.
 *
 * Two separate questions, deliberately not merged, because they have different
 * owners and different fixes:
 *
 *  - Is the DECLARATION right? A data problem, and the one that made this module
 *    necessary. Fixing it is editing a number. Tolerance is in bpm, because that
 *    is the unit the error is declared in.
 *
 *  - Can an integer frame grid REPRESENT that tempo over the horizon? A limit of
 *    whole frames, which no amount of correct data removes — at 60fps a beat is
 *    ~28 frames, so the representable tempos are 60*fps/n and nothing else.
 *    Measured in BEATS, not milliseconds: the millisecond figure grows with the
 *    horizon by construction, so a millisecond tolerance is a length tolerance in
 *    disguise, and one picked for an 801-frame film would fail a 1950-frame one
 *    for a reason no data fix can address. One beat is the natural bound — past
 *    that the grid is pointing at a different beat than the one it started on.
 */
export const tempoAgreement = (
  declared: number,
  fit: BpmFit,
  limits: {bpmTolerance: number; maxDriftBeats: number},
  g: BeatGrid
): {declaredVsMeasured: number; representable: boolean; reasons: string[]} => {
  const reasons: string[] = [];
  const diff = bpmDisagreement(declared, fit);
  if (Math.abs(diff) > limits.bpmTolerance) {
    reasons.push(
      `declared ${declared.toFixed(2)} bpm differs from the fitted ${fit.bpm.toFixed(2)} bpm ` +
        `by ${diff >= 0 ? '+' : ''}${diff.toFixed(2)} (tolerance ${limits.bpmTolerance})`
    );
  }
  if (Math.abs(g.driftBeatsAtHorizon) > limits.maxDriftBeats) {
    reasons.push(
      `the integer grid can only play ${g.representedBpm.toFixed(3)} bpm, which drifts ` +
        `${g.driftBeatsAtHorizon >= 0 ? '+' : ''}${g.driftBeatsAtHorizon.toFixed(2)} beats ` +
        `(${g.driftMsAtHorizon.toFixed(0)} ms) by the last boundary — more than ` +
        `${limits.maxDriftBeats} beat`
    );
  }
  return {declaredVsMeasured: diff, representable: reasons.length === 0, reasons};
};
