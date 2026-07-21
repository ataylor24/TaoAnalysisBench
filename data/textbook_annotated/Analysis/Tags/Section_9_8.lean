import Analysis.Section_9_8

attribute [aesop safe] Chapter9.AntitoneOn.iff
attribute [aesop unsafe 50%] Chapter9.BddOn.of_antitone
attribute [grind →] Chapter9.BddOn.of_antitone
attribute [aesop unsafe 50%] Chapter9.BddOn.of_monotone
attribute [grind →] Chapter9.BddOn.of_monotone
attribute [aesop safe] Chapter9.ContinuousAt.of_f_9_8_5
attribute [aesop safe] Chapter9.ContinuousAt.of_f_9_8_5'
attribute [aesop unsafe 50%] Chapter9.IsMaxOn.of_antitone_on_compact
attribute [aesop unsafe 50%] Chapter9.IsMaxOn.of_monotone_on_compact
attribute [aesop unsafe 50%] Chapter9.IsMaxOn.of_strictantitone_on_compact
attribute [aesop unsafe 50%] Chapter9.IsMaxOn.of_strictmono_on_compact
attribute [aesop unsafe 10%] Chapter9.MonotoneOn.exist_inverse
attribute [aesop safe] Chapter9.MonotoneOn.iff
attribute [aesop safe] Chapter9.StrictAntitone.iff
attribute [aesop safe] Chapter9.StrictMono.iff
attribute [aesop safe] Chapter9.StrictMonoOn.of_f_9_8_5
attribute [aesop unsafe 30%] Chapter9.mono_of_continuous_inj
