import Analysis.Section_2_2

attribute [aesop unsafe 30%] Chapter2.Nat.add_assoc
attribute [grind =_] Chapter2.Nat.add_assoc
attribute [aesop unsafe 30%] Chapter2.Nat.add_comm
attribute [grind =_] Chapter2.Nat.add_comm
attribute [aesop safe] Chapter2.Nat.add_eq_zero
attribute [grind →] Chapter2.Nat.add_eq_zero
attribute [aesop unsafe 50%] Chapter2.Nat.add_ge_add_left
attribute [grind ←] Chapter2.Nat.add_ge_add_left
attribute [aesop unsafe 50%] Chapter2.Nat.add_ge_add_right
attribute [grind ←] Chapter2.Nat.add_ge_add_right
attribute [aesop unsafe 50%] Chapter2.Nat.add_le_add_left
attribute [grind ←] Chapter2.Nat.add_le_add_left
attribute [aesop unsafe 50%] Chapter2.Nat.add_le_add_right
attribute [grind ←] Chapter2.Nat.add_le_add_right
attribute [aesop unsafe 50%] Chapter2.Nat.add_left_cancel
attribute [grind →] Chapter2.Nat.add_left_cancel
attribute [aesop safe] Chapter2.Nat.add_pos_left
attribute [aesop safe] Chapter2.Nat.add_pos_right
attribute [simp] Chapter2.Nat.add_succ
attribute [simp] Chapter2.Nat.add_zero
attribute [aesop safe] Chapter2.Nat.ge_antisymm
attribute [grind →] Chapter2.Nat.ge_antisymm
attribute [simp] Chapter2.Nat.ge_iff_le
attribute [aesop safe] Chapter2.Nat.ge_refl
attribute [aesop unsafe 50%] Chapter2.Nat.ge_trans
attribute [grind →] Chapter2.Nat.ge_trans
attribute [simp] Chapter2.Nat.gt_iff_lt
attribute [simp] Chapter2.Nat.isPos_iff
attribute [simp] Chapter2.Nat.le_iff
attribute [aesop unsafe 30%] Chapter2.Nat.le_iff_lt_or_eq
attribute [aesop unsafe 80%] Chapter2.Nat.le_of_lt
attribute [grind →] Chapter2.Nat.le_of_lt
attribute [aesop safe] Chapter2.Nat.le_refl
attribute [aesop unsafe 50%] Chapter2.Nat.le_trans
attribute [grind →] Chapter2.Nat.le_trans
attribute [aesop unsafe 30%] Chapter2.Nat.lt_iff_add_pos
attribute [aesop unsafe 50%] Chapter2.Nat.lt_iff_succ_le
attribute [grind ←] Chapter2.Nat.lt_iff_succ_le
attribute [aesop unsafe 50%] Chapter2.Nat.lt_of_le_of_lt
attribute [grind →] Chapter2.Nat.lt_of_le_of_lt
attribute [aesop safe] Chapter2.Nat.ne_of_gt
attribute [grind →] Chapter2.Nat.ne_of_gt
attribute [aesop safe] Chapter2.Nat.ne_of_lt
attribute [grind →] Chapter2.Nat.ne_of_lt
attribute [aesop safe] Chapter2.Nat.not_lt_of_gt
attribute [grind →] Chapter2.Nat.not_lt_of_gt
attribute [aesop safe] Chapter2.Nat.not_lt_self
attribute [grind →] Chapter2.Nat.not_lt_self
attribute [simp] Chapter2.Nat.one_add
attribute [simp] Chapter2.Nat.succ_add
attribute [aesop safe] Chapter2.Nat.succ_gt_self
attribute [aesop unsafe 20%] Chapter2.Nat.trichotomous
attribute [simp] Chapter2.Nat.two_add
attribute [aesop unsafe 20%] Chapter2.Nat.uniq_succ_eq
attribute [simp] Chapter2.Nat.zero_add
attribute [aesop safe] Chapter2.Nat.zero_le
