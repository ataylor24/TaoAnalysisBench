import Analysis.Section_8_5

attribute [simp] Chapter8.IsMax.iff
attribute [aesop unsafe 60%] Chapter8.IsMax.ofFinite
attribute [simp] Chapter8.IsMin.iff
attribute [simp] Chapter8.IsMin.iff_lowerbound
attribute [simp] Chapter8.IsMin.iff_lowerbound'
attribute [aesop unsafe 60%] Chapter8.IsMin.ofFinite
attribute [simp] Chapter8.IsStrictUpperBound.iff
attribute [aesop safe] Chapter8.IsTotal.subset
attribute [grind →] Chapter8.IsTotal.subset
attribute [aesop safe] Chapter8.IsTotal.subtype
attribute [simp] Chapter8.IsUpperBound.iff
attribute [aesop safe] Chapter8.Lex'.WellFoundedLT
attribute [aesop unsafe 20%] Chapter8.WellFoundedLT.iff
attribute [aesop unsafe 20%] Chapter8.WellFoundedLT.iff'
attribute [aesop safe] Chapter8.WellFoundedLT.ofFinite
attribute [aesop unsafe 10%] Chapter8.WellFoundedLT.partialOrder
attribute [aesop unsafe 20%] Chapter8.WellFoundedLT.strong_induction
attribute [aesop safe] Chapter8.WellFoundedLT.subset
attribute [grind →] Chapter8.WellFoundedLT.subset
attribute [aesop unsafe 10%] Chapter8.Zorns_lemma
