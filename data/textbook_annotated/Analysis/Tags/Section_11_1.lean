import Analysis.Section_11_1

attribute [aesop safe] Chapter11.Bornology.IsBounded.of_boundedInterval
attribute [aesop safe] Chapter11.BoundedInterval.Ioo_subset
attribute [simp] Chapter11.BoundedInterval.coe_empty
attribute [aesop safe] Chapter11.BoundedInterval.dist_le_length
attribute [grind →] Chapter11.BoundedInterval.dist_le_length
attribute [simp] Chapter11.BoundedInterval.empty_of_lt
attribute [simp] Chapter11.BoundedInterval.inter_eq
attribute [aesop unsafe 60%] Chapter11.BoundedInterval.join_Icc_Ioc
attribute [grind →] Chapter11.BoundedInterval.join_Icc_Ioc
attribute [aesop unsafe 60%] Chapter11.BoundedInterval.join_Icc_Ioo
attribute [grind →] Chapter11.BoundedInterval.join_Icc_Ioo
attribute [aesop unsafe 60%] Chapter11.BoundedInterval.join_Ico_Icc
attribute [grind →] Chapter11.BoundedInterval.join_Ico_Icc
attribute [aesop unsafe 60%] Chapter11.BoundedInterval.join_Ico_Ico
attribute [grind →] Chapter11.BoundedInterval.join_Ico_Ico
attribute [aesop unsafe 60%] Chapter11.BoundedInterval.join_Ioc_Ioc
attribute [grind →] Chapter11.BoundedInterval.join_Ioc_Ioc
attribute [aesop unsafe 60%] Chapter11.BoundedInterval.join_Ioc_Ioo
attribute [grind →] Chapter11.BoundedInterval.join_Ioc_Ioo
attribute [aesop unsafe 60%] Chapter11.BoundedInterval.join_Ioo_Icc
attribute [grind →] Chapter11.BoundedInterval.join_Ioo_Icc
attribute [aesop unsafe 60%] Chapter11.BoundedInterval.join_Ioo_Ico
attribute [grind →] Chapter11.BoundedInterval.join_Ioo_Ico
attribute [aesop safe] Chapter11.BoundedInterval.le_max
attribute [aesop safe] Chapter11.BoundedInterval.length_nonneg
attribute [simp] Chapter11.BoundedInterval.length_of_empty
attribute [simp] Chapter11.BoundedInterval.length_of_subsingleton
attribute [aesop safe] Chapter11.BoundedInterval.max_le_iff
attribute [grind →] Chapter11.BoundedInterval.max_le_iff
attribute [simp] Chapter11.BoundedInterval.mem_iff
attribute [simp] Chapter11.BoundedInterval.mem_inter
attribute [simp] Chapter11.BoundedInterval.set_Icc
attribute [simp] Chapter11.BoundedInterval.set_Ico
attribute [simp] Chapter11.BoundedInterval.set_Ioc
attribute [simp] Chapter11.BoundedInterval.set_Ioo
attribute [aesop safe] Chapter11.BoundedInterval.subset_Icc
attribute [simp] Chapter11.BoundedInterval.subset_iff
attribute [simp] Chapter11.Partition.intervals_of_add_empty
attribute [simp] Chapter11.Partition.intervals_of_bot
attribute [simp] Chapter11.Partition.intervals_of_join
attribute [simp] Chapter11.Partition.sum_of_length
