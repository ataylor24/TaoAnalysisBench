import Analysis.Appendix_B_2

attribute [aesop safe] AppendixB.NNRealDecimal.not_inj
attribute [aesop unsafe 20%] AppendixB.NNRealDecimal.surj
attribute [aesop safe] AppendixB.NNRealDecimal.toNNReal_conv
attribute [aesop unsafe 10%] AppendixB.RealDecimal.inj_nonterminating
attribute [simp] AppendixB.RealDecimal.not_inj_one
attribute [aesop unsafe 10%] AppendixB.RealDecimal.not_inj_terminating
attribute [aesop unsafe 20%] AppendixB.RealDecimal.surj
