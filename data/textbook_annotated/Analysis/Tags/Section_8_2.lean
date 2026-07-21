import Analysis.Section_8_2

attribute [aesop safe] Chapter8.AbsConvergent'.countable_supp
attribute [simp] Chapter8.AbsConvergent'.iff_Summable
attribute [aesop unsafe 50%] Chapter8.AbsConvergent'.of_countable
attribute [aesop safe] Chapter8.AbsConvergent'.of_finite
attribute [aesop safe] Chapter8.AbsConvergent'.subtype
attribute [aesop safe] Chapter8.AbsConvergent.comp
attribute [aesop unsafe 50%] Chapter8.AbsConvergent.iff
attribute [aesop unsafe 50%] Chapter8.AbsConvergent.mk
attribute [simp] Chapter8.Filter.Eventually.int_natCast_atTop
attribute [simp] Chapter8.Filter.Tendsto.int_natCast_atTop
attribute [simp] Chapter8.Finset.Icc_empty
attribute [simp] Chapter8.Finset.Icc_eq_cast
attribute [aesop safe] Chapter8.Sum'.add
attribute [simp] Chapter8.Sum'.eq_tsum
attribute [aesop safe] Chapter8.Sum'.of_comp
attribute [aesop unsafe 30%] Chapter8.Sum'.of_countable_supp
attribute [simp] Chapter8.Sum'.of_disjoint_union
attribute [aesop unsafe 50%] Chapter8.Sum'.of_finsupp
attribute [simp] Chapter8.Sum'.of_univ
attribute [aesop safe] Chapter8.Sum'.smul
attribute [aesop safe] Chapter8.Sum'.sub
attribute [aesop safe] Chapter8.Sum.eq
attribute [aesop safe] Chapter8.Sum.of_comp
attribute [simp] Chapter8.Sum.of_finite
attribute [aesop unsafe 20%] Chapter8.divergent_parts_of_divergent
attribute [aesop unsafe 10%] Chapter8.permute_convergesTo_of_divergent
attribute [aesop unsafe 10%] Chapter8.permute_diverges_of_divergent
attribute [aesop unsafe 10%] Chapter8.permute_diverges_of_divergent'
attribute [aesop unsafe 20%] Chapter8.sum_comm
attribute [aesop unsafe 20%] Chapter8.sum_of_sum_of_AbsConvergent
attribute [aesop unsafe 20%] Chapter8.sum_of_sum_of_AbsConvergent'
attribute [aesop unsafe 20%] Chapter8.sum_of_sum_of_AbsConvergent_nonneg
