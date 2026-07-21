import Analysis.Section_6_2

attribute [aesop safe] Chapter5.ExtendedReal.coe_inj
attribute [aesop unsafe 20%] Chapter5.ExtendedReal.coe_surj
attribute [aesop unsafe 20%] EReal.def
attribute [grind =] EReal.inf_eq_neg_sup
attribute [aesop safe] EReal.inf_ge_upper
attribute [grind →] EReal.inf_ge_upper
attribute [aesop unsafe 50%] EReal.infinite_iff_not_finite
attribute [aesop safe] EReal.infty_neq_neg_infty
attribute [aesop unsafe 20%] EReal.le_iff
attribute [aesop safe] EReal.lt_iff
attribute [aesop safe] EReal.mem_ge_inf
attribute [grind →] EReal.mem_ge_inf
attribute [aesop safe] EReal.mem_le_sup
attribute [grind →] EReal.mem_le_sup
attribute [aesop safe] EReal.neg_of_lt
attribute [grind →] EReal.neg_of_lt
attribute [simp] EReal.neg_of_real
attribute [aesop safe] EReal.not_gt_and_eq
attribute [aesop safe] EReal.not_lt_and_eq
attribute [aesop safe] EReal.not_lt_and_gt
attribute [aesop safe] EReal.real_neq_infty
attribute [aesop safe] EReal.real_neq_neg_infty
attribute [aesop safe] EReal.refl
attribute [aesop safe] EReal.sup_le_upper
attribute [grind →] EReal.sup_le_upper
attribute [simp] EReal.sup_of_bounded_nonempty
attribute [simp] EReal.sup_of_empty
attribute [simp] EReal.sup_of_infty_mem
attribute [grind =] EReal.sup_of_neg_infty_mem
attribute [simp] EReal.sup_of_unbounded_nonempty
attribute [aesop unsafe 50%] EReal.trans
attribute [grind →] EReal.trans
attribute [aesop unsafe 20%] EReal.trichotomy
