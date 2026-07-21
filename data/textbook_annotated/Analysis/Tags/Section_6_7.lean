import Analysis.Section_6_7

attribute [aesop unsafe 20%] Chapter6.Real.eq_lim_of_rat
attribute [simp] Chapter6.Real.ratPow_add
attribute [aesop unsafe 50%] Chapter6.Real.ratPow_mono
attribute [simp] Chapter6.Real.ratPow_mono_of_gt_one
attribute [simp] Chapter6.Real.ratPow_mono_of_lt_one
attribute [simp] Chapter6.Real.ratPow_mul
attribute [simp] Chapter6.Real.ratPow_neg
attribute [aesop safe] Chapter6.Real.ratPow_nonneg
attribute [simp] Chapter6.Real.ratPow_ratPow
attribute [aesop safe] Chapter6.Real.ratPow_tendsto_rpow
attribute [aesop unsafe 50%] Chapter6.Real.rpow_eq_lim_ratPow
attribute [simp] Chapter6.Real.rpow_of_rat_eq_ratPow
attribute [aesop safe] Chapter6.ratPow_continuous
attribute [aesop unsafe 30%] Chapter6.ratPow_lim_uniq
