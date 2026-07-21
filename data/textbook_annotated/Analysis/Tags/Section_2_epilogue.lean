import Analysis.Section_2_epilogue

attribute [aesop unsafe 50%] Chapter2.Nat.pow_eq_pow
attribute [simp] Chapter2.Nat.succ_toNat
attribute [simp] Chapter2.Nat.zero_toNat
attribute [aesop safe] PeanoAxioms.Equiv.uniq
attribute [aesop unsafe 20%] PeanoAxioms.Nat.recurse_uniq
attribute [aesop safe] PeanoAxioms.natCast_injective
attribute [aesop safe] PeanoAxioms.natCast_surjective
