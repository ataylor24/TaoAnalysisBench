import Analysis.Section_9_6

attribute [aesop unsafe 50%] Chapter9.BddAboveOn.isMaxOn
attribute [grind →] Chapter9.BddAboveOn.isMaxOn
attribute [aesop unsafe 50%] Chapter9.BddBelowOn.isMinOn
attribute [grind →] Chapter9.BddBelowOn.isMinOn
attribute [aesop unsafe 50%] Chapter9.BddOn.iff
attribute [aesop unsafe 50%] Chapter9.BddOn.iff'
attribute [aesop unsafe 60%] Chapter9.BddOn.of_bounded
attribute [aesop unsafe 20%] Chapter9.BddOn.of_continuous_on_compact
attribute [aesop unsafe 20%] Chapter9.IsMaxOn.of_continuous_on_compact
attribute [aesop unsafe 20%] Chapter9.IsMinOn.of_continuous_on_compact
attribute [aesop unsafe 20%] Chapter9.sInf.of_continuous_on_compact
attribute [aesop safe] Chapter9.sInf.of_isMinOn
attribute [grind →] Chapter9.sInf.of_isMinOn
attribute [aesop unsafe 20%] Chapter9.sSup.of_continuous_on_compact
attribute [aesop safe] Chapter9.sSup.of_isMaxOn
attribute [grind →] Chapter9.sSup.of_isMaxOn
attribute [aesop safe] Chapter9.why_7_6_3
