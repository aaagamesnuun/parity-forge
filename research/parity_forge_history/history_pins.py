"""Literal Plan-0013 history pins; no executable legacy import.

Copied from the frozen atlas_history source. Tests compare these literals with
that source and authenticate both cutoff Git trees without opening held-out
experiment members. This module grants no artifact-reading capability.
"""

ATLAS_HISTORY_CUTOFF_COMMIT_V1 = (
    "6910b6cc03c03701c56bc44d98bb9cf8ac5bf03c"
)

ATLAS_HISTORY_CUTOFF_TREE_V1 = (
    "6bc44b1d51fcf67f691e5cc8106b1b1140947007"
)

ATLAS_HISTORY_CUTOFF_ID_V1 = (
    "git-commit:"
    + ATLAS_HISTORY_CUTOFF_COMMIT_V1
    + ";git-tree:"
    + ATLAS_HISTORY_CUTOFF_TREE_V1
)

ATLAS_HISTORY_PROJECTION_ID_V1 = "plan0013-prior-gameplay-exposure-v1"

ATLAS_HISTORY_SOURCE_COUNT_V1 = 66

ATLAS_HISTORY_DEFINITION_OCCURRENCE_COUNT_V1 = 2_243

ATLAS_HISTORY_MALFORMED_DEFINITION_LIKE_COUNT_V1 = 1

ATLAS_HISTORY_UNIQUE_DEFINITION_COUNT_V1 = 1_172

ATLAS_HISTORY_UNIQUE_D4_COUNT_V1 = 1_168

ATLAS_HISTORY_SCHEMA_OCCURRENCE_COUNTS_V1 = ((1, 1_665), (2, 258), (3, 320))

ATLAS_HISTORY_DEFINITION_BEARING_SOURCE_COUNT_V1 = 16

ATLAS_HISTORY_ZERO_DEFINITION_SOURCE_COUNT_V1 = 50

ATLAS_HISTORY_DEFINITION_HASH_REFERENCE_COUNT_V1 = 5_297

ATLAS_HISTORY_UNIQUE_DEFINITION_HASH_REFERENCE_COUNT_V1 = 1_172

ATLAS_HISTORY_D4_HASH_REFERENCE_COUNT_V1 = 2_951

ATLAS_HISTORY_UNIQUE_D4_HASH_REFERENCE_COUNT_V1 = 896

ATLAS_HISTORY_SOURCE_ATTESTATION_ROOT_V1 = (
    "c24bb29b2ddf6b837b25355face9060667b1c99e768a7b103b0c28d6a2f0abe6"
)

ATLAS_HISTORY_UNIQUE_DEFINITION_ROOT_V1 = (
    "45722420316fcc04d8fe8a862615928ded9500f4deec2376d910e29accf84c3d"
)

ATLAS_HISTORY_UNIQUE_D4_ROOT_V1 = (
    "7e2984ac4aeb5e9f659c0441eeca45a6febad4506ff79d4c55f6708aa7a6d1af"
)

ATLAS_HISTORY_PROJECTION_ROOT_V1 = (
    "b7461dbe226d436e1fd50a33cb0987efdff225626aea8105e99daa9eb4f59e9a"
)

_EXPECTED_MALFORMED_DEFINITION_LOCATIONS_V1 = (
    "experiments/corpora/static-v1/corpus.json#/cases/6/definition",
)

ATLAS_HISTORY_INVENTORY_V1 = (
    (
        "experiments/corpora/capture-boundary-v1/exclusion-ledger.json",
        "841789e168baf7446072d189ca272783c944d36d71630421f9fe70ec6a3865ea",
        480_270,
    ),
    (
        "experiments/corpora/capture-boundary-v1/manifest-attempt.json",
        "33dcc61b35526d07b760c5138049800910fff860e7ed305155ab3ecfad538d17",
        1_227,
    ),
    (
        "experiments/corpora/capture-boundary-v1/manifest-reservation.json",
        "175ec078aec69d781a3d4060a714ce9fcaf81ed6c60ef2c76edfa6b94a22692f",
        243,
    ),
    (
        "experiments/corpora/capture-boundary-v1/manifest.json",
        "e1b0f6a7aed05264133964954380e6d59b200cfe903888b2d279f2a626ebd78f",
        256_761,
    ),
    (
        "experiments/corpora/capture-boundary-v1/manifest.lock.json",
        "5d12680fc87db2cba19aa1b0a160a1eaf3c51be150ad759c44dc365df0d23dc7",
        434,
    ),
    (
        "experiments/corpora/capture-v1/manifest-attempt.json",
        "5f65911bc875495b81f5a9032c1ea218d7214402eb40f8ac814a54861b197c8f",
        1_312,
    ),
    (
        "experiments/corpora/capture-v1/manifest-reservation.json",
        "3f67d49fe50e2c6897a689c9c3b9bd8bfbd1154c961a6e49b4608aa7fd7c2cbe",
        239,
    ),
    (
        "experiments/corpora/capture-v1/manifest.json",
        "6bc466453f60bc4ae2a6401fc76a77eebe4a7ebee82111e53ac4463400588f4f",
        490_512,
    ),
    (
        "experiments/corpora/capture-v1/manifest.lock.json",
        "496a87ac1f169d7d6b19c29bf176a7af6f11ddc481578fcdab889b46f79b429f",
        297,
    ),
    (
        "experiments/corpora/exact-v1/manifest.json",
        "a83141ac47cdf92b701d5b79eae12136682bcd214a323fa49cb98358b709f35e",
        622,
    ),
    (
        "experiments/corpora/landscape-v1/manifest-attempt.json",
        "6f720bc50c0c1fd16e0ee6277a81c47fb62e5340b5f714501c0636c0508186f5",
        2_316,
    ),
    (
        "experiments/corpora/landscape-v1/manifest.json",
        "f407aefb5fdb8c926db282ff90d2feb1a8666cda3fdbd6925b9f5cc07abd87b1",
        836_483,
    ),
    (
        "experiments/corpora/landscape-v1/manifest.lock.json",
        "f92abf7b30211c2a6ccbab5aa1bb7a2fd6c598375b87b8211d5f72891da6d6f0",
        287,
    ),
    (
        "experiments/corpora/play-v1/manifest.json",
        "01a0b92171f6819de034417fd3fbafa43815e3c130dfc09715c40eb5b5019569",
        865,
    ),
    (
        "experiments/corpora/stalemate-v1/manifest-attempt.json",
        "8dc5f68fe92dcbdf0fd93df611361ce50cdd1e630a3625e69031bceaa97ee9a7",
        1_247,
    ),
    (
        "experiments/corpora/stalemate-v1/manifest-reservation.json",
        "1fd5b7ed224a86179ecb9caf9ae58c150212764baf7545998d6c9223dfcf2007",
        243,
    ),
    (
        "experiments/corpora/stalemate-v1/manifest.json",
        "ed9a9b93ad234f4375ded0e135f5436c82fb127988784a86aa33ab4f776ff176",
        516_811,
    ),
    (
        "experiments/corpora/stalemate-v1/manifest.lock.json",
        "979d0f4a0cfe2a70369af634d47f5d621d52edd7ae624c2e1aba198d7b52851f",
        301,
    ),
    (
        "experiments/corpora/static-v1/corpus.json",
        "4ad81a4019f072a6f47d88e86f1761c0f55ef792f647d1348d292085496ce208",
        6_160,
    ),
    (
        "experiments/corpora/two-runner-v1/exclusion-ledger.json",
        "b38b2d1e2bd5b3faa0c5cdb86580e408547faa4bef819eeb9c3feb5143b440a0",
        131_707,
    ),
    (
        "experiments/corpora/two-runner-v1/manifest-attempt.json",
        "9600801cf9bd7777cb31c689da276c5440cf1165694c17f39109cba4840c306c",
        1_094,
    ),
    (
        "experiments/corpora/two-runner-v1/manifest-reservation.json",
        "c4fb2a1b5478d77048e2608615e94ab1836c18759d99d64f11ea597cb7af501c",
        231,
    ),
    (
        "experiments/corpora/two-runner-v1/manifest.json",
        "3b7757ade9bd745eb1aff838455927115005dd8efe4d96ebaef51af213d228b9",
        272_179,
    ),
    (
        "experiments/corpora/two-runner-v1/manifest.lock.json",
        "fc2b14f0981da9a746e60657f3a333f6ee92dbafb9c24e5157b5626e90ceee86",
        520,
    ),
    (
        "experiments/runs/.capture-boundary-v1-fixed-depth5.reservation.json",
        "f58973e92a07322938ff91c1219e381226c270bc98da919b25691edf7854e01c",
        259,
    ),
    (
        "experiments/runs/.capture-boundary-v1-paired-exact.reservation.json",
        "83e42c57ea25b9fcbd02243bbc89482f0f26f0bc678f2afa0c3462bdfec20e3f",
        258,
    ),
    (
        "experiments/runs/.capture-v1-interaction-stress.reservation.json",
        "6a75217debf0ac2f6ada42f35f8e823077a59c1bdeac6ab4bf9f10e4e279df89",
        247,
    ),
    (
        "experiments/runs/.capture-v1-paired-raw-exact.reservation.json",
        "dcd65a756e5ac5c40e0bc7738df0806f115f86cb7fde8b81d123ddcd57f7ef43",
        238,
    ),
    (
        "experiments/runs/.landscape-v1-draw-stress.reservation.json",
        "2193987f2b727a255082f3e0ff62c8a3aa46e49c3e2a5e1a6c24ed7689585771",
        239,
    ),
    (
        "experiments/runs/.landscape-v1-raw-exact.reservation.json",
        "e8835e64e62cbd2cd12595a60babb0a9c8637ee5bfb7dce579d839a5ccf75d27",
        235,
    ),
    (
        "experiments/runs/.stalemate-v1-draw-stress.reservation.json",
        "5bc893863af383123c3bac13aad4fbc203f2e52dd273dc34fdeea8f6bd0ffe84",
        244,
    ),
    (
        "experiments/runs/.stalemate-v1-paired-raw-exact.reservation.json",
        "82cc762f67b1cca33d4bdebc93316ad414f7e878ed13f0e7c399838753a44da4",
        242,
    ),
    (
        "experiments/runs/.two-runner-v1-fixed-depth5.reservation.json",
        "566e082e5f1833f92957ff60d3a7b7ec1253bfc3f62ad6b39d5d0eb3bf005863",
        247,
    ),
    (
        "experiments/runs/.two-runner-v1-paired-exact.reservation.json",
        "c30c6b3ae7b414596e909ea714eb1dfe26b6657114c844d39df43a6addd2b2bf",
        246,
    ),
    (
        "experiments/runs/20260830T153256441950Z-static-4ad81a40/run.json",
        "e4c34a5b5562b2780cb5c8a6dae4b974dd3eeed21d5123fb437eb1b95fc0433d",
        4_440,
    ),
    (
        "experiments/runs/20260830T153616787888Z-play-1c478ea4/run.json",
        "908146e2636aea8ccdd701e8256345cc2944ab37883d4da4c6b23c789ecf3ecd",
        561_149,
    ),
    (
        "experiments/runs/20260830T153746479973Z-solve-1c478ea4/run.json",
        "7de132fad005f79f9f257faae3e9e98d644c90ed7084f7479a8d1908c32f9ac4",
        4_529,
    ),
    (
        "experiments/runs/20260830T154155824053Z-batch-g20260831/run.json",
        "b664e133cda42b494d7222735999f0d7b490d9e0108e13743cef8dd20824bb97",
        448_323,
    ),
    (
        "experiments/runs/20260830T154309225370Z-batch-g20260831/run.json",
        "374bfc58030f0acce32a3edd7ff3d10764fb001d130eda4b1da086550b7cb0f5",
        471_889,
    ),
    (
        "experiments/runs/20260830T154446539528Z-audit-374bfc58/run.json",
        "6f86cb959d2ec2fd0bb2ff1c27859bec48898be2ad471f067bd07d084e911d0e",
        33_362,
    ),
    (
        "experiments/runs/20260830T154624122230Z-calibrate-f27833e8/run.json",
        "f4f5b05999aed7913cfab3541ffa0978884a399e7886e1ed2e5a627010136795",
        28_803,
    ),
    (
        "experiments/runs/20260830T154733530838Z-calibrate-f27833e8/run.json",
        "f72591218a5995696c884247b49282e6a572bebb2c4a3fa59d6d23537dd7d708",
        28_577,
    ),
    (
        "experiments/runs/20260830T184008717197Z-strong-g20260901/attempt.json",
        "72f96e0dc98109b526fce97950233d80486a2c44ac48511630a0b7dbe2a368aa",
        10_369,
    ),
    (
        "experiments/runs/20260830T184008717197Z-strong-g20260901/run.json",
        "cdf26f22c93a95f70e413e28257a6afddfaecf21008507a6557e019f2c5357dc",
        598_637,
    ),
    (
        "experiments/runs/20260830T184737002247Z-blind-depth5-cdf26f22/attempt.json",
        "c89d7266ec4c1d32d3ac92907921727630e3f4fa8a7c496a6debb7e0c5d6a32f",
        1_365,
    ),
    (
        "experiments/runs/20260830T184737002247Z-blind-depth5-cdf26f22/run.json",
        "51d4bf0afd31019d6886ae26e0d45ca0d32f2964528918ab13e07001e8607bea",
        25_193,
    ),
    (
        "experiments/runs/20260830T200230881318Z-landscape-f407aefb/attempt.json",
        "6165fc68a2801da00eaa07cc76144cec1192575093abfb3d5e278fda7130b201",
        1_631,
    ),
    (
        "experiments/runs/20260830T200230881318Z-landscape-f407aefb/run.json",
        "1edf571bc140a0cd586340eafee2306bccf6ca3a0816f8809b07edc9ef1a9fa4",
        2_739_400,
    ),
    (
        "experiments/runs/20260830T200513661140Z-draw-stress-1edf571b/attempt.json",
        "9bbb5b298ce3b8f90583acc115c0f59c6aa377a09fb099a9e3f7c97832ad934b",
        1_721,
    ),
    (
        "experiments/runs/20260830T200513661140Z-draw-stress-1edf571b/run.json",
        "172c36f733ba4ba7cf214369141700d6af17b4c58365d16bb90bcbdd76af3588",
        65_139,
    ),
    (
        "experiments/runs/20260830T214033891685Z-stalemate-ed9a9b93/attempt.json",
        "ab5efa12c6d295cf4970c6e435df76e60d2a5296da9e9bd70f57198eed6145ee",
        2_163,
    ),
    (
        "experiments/runs/20260830T214033891685Z-stalemate-ed9a9b93/run.json",
        "239ad79d8009be95362efa956cbd356130faa3cd0223df5e897de0fa9d04335c",
        1_314_571,
    ),
    (
        "experiments/runs/20260830T214159802995Z-stalemate-stress-239ad79d/attempt.json",
        "cdacc0a80b41e52feada846f77768dd437c9b65e38d4dcd219d5a89cc3b7a783",
        1_858,
    ),
    (
        "experiments/runs/20260830T214159802995Z-stalemate-stress-239ad79d/run.json",
        "c05175254b16386f6c8c060f8c43a925ffd8f30a52f5a78d3d0cc0c6b95bb88f",
        32_578,
    ),
    (
        "experiments/runs/20260830T225920216640Z-capture-6bc46645/attempt.json",
        "29144435347a08c027d2961be48eccb588353f4778512ff349f52a644d055959",
        2_283,
    ),
    (
        "experiments/runs/20260830T225920216640Z-capture-6bc46645/run.json",
        "e4fc6e97d6307d025784487956911c9e0af7ea41365cb5955520f2a31c3f21af",
        16_708_265,
    ),
    (
        "experiments/runs/20260830T230308952280Z-capture-stress-e4fc6e97/attempt.json",
        "71e0e339cb96ecc3f7bcb49b5add6992ad8f9b40988cbfeb3b3383afae8462d3",
        1_866,
    ),
    (
        "experiments/runs/20260830T230308952280Z-capture-stress-e4fc6e97/run.json",
        "9d12a317a25d2393a0174272bfa1e858592f240f9211f5fb7d3e4a5408d4f742",
        1_980_251,
    ),
    (
        "experiments/runs/20260831T012026857459Z-capture-boundary-exact-e1b0f6a7/attempt.json",
        "b477f26932c917df3573c6ed7772bc3e932868d15d6df40e03c1c6c003f7e234",
        1_197,
    ),
    (
        "experiments/runs/20260831T012026857459Z-capture-boundary-exact-e1b0f6a7/run.json",
        "cbf2ccc3235c92990d6d42377c7c81b77d4463c28b6a97a15d2ce4c0d109f5f4",
        727_579,
    ),
    (
        "experiments/runs/20260831T012251133134Z-capture-boundary-depth5-cbf2ccc3/attempt.json",
        "75ab0f977000857961260257b92e8c1d3f3a2974d60f9fd498ce3e379c0a29b7",
        2_179,
    ),
    (
        "experiments/runs/20260831T012251133134Z-capture-boundary-depth5-cbf2ccc3/run.json",
        "40a800b1d9f4537d7c3c783136230471adfa71ec75938d3aa0289592972d5782",
        8_622_601,
    ),
    (
        "experiments/runs/20260831T042721207815Z-two-runner-exact-3b7757ad/attempt.json",
        "1694242d04f888479a13bf05505fae6791b4d2876376a0874be821de90655a71",
        1_345,
    ),
    (
        "experiments/runs/20260831T042721207815Z-two-runner-exact-3b7757ad/run.json",
        "2353bfb8dbf545d6c3430a998b5fe60c5db9822c28c965f7a2adbacce0844e39",
        1_333_308,
    ),
    (
        "experiments/runs/20260831T043600138223Z-two-runner-depth5-2353bfb8/attempt.json",
        "505d18cba31bb182dd25f45668824bf4a8a774f12de4eb2c5be8442f30e0189e",
        2_261,
    ),
    (
        "experiments/runs/20260831T043600138223Z-two-runner-depth5-2353bfb8/run.json",
        "dd77cfbd1cb76763ed394d767ce5c296191d25f2589d0a48819de242526f8cda",
        27_597_646,
    ),
)

PLAN0012_SYNTHETIC_BENCHMARK_ROOT_V1 = (
    "6789f97e7f0948df9fa66f75933c061a08e029ce49e9d9da33ae57a7b4a59a33"
)

ATLAS_SYNTHETIC_PROJECTION_ID_V1 = (
    "plan0013-plan0012-synthetic-fixture-exposure-v1"
)

ATLAS_SYNTHETIC_CUTOFF_ID_V1 = (
    "plan0012-telemetry-benchmark-root:"
    + PLAN0012_SYNTHETIC_BENCHMARK_ROOT_V1
)

PLAN0012_SYNTHETIC_FIXTURE_IDENTITIES_V1 = (
    (
        "capture-eliminate-one-sided-b-v1",
        "ccbf7cfe2076e6d6fbd66aa35f0a9fd1d760f7510a4ef0a1f3b0e5e4b1e66eda",
        "bb61383bd417dc9fa32c7d1717c309f25b8e490a0f6c39051e3db6ac4431770a",
        519,
    ),
    (
        "convert-immediate-reconvergence-v1",
        "fd2768bc19220de4c5e0c18040982524b034e0215279d8b51b79b9a5c513a079",
        "01425a63068bbbb5720a1dd56ffb5b9b7f38f3905f56ee9b77ae7333c110c9ed",
        595,
    ),
    (
        "hop-opponent-dependency-without-direct-effect-v1",
        "08536bcae39cf0f8eaaf541ba4e570288572cb9bedac93c43041a2ea0219fd84",
        "454de6d824d820179faad6cde1023804bb2ff9be73d959fca8662836be38f85a",
        494,
    ),
    (
        "initial-stuck-zero-v1",
        "cb5e91d6873bc2fc847aac453608f041ac2f41d65f6f1921393fd83989d9c809",
        "5aecc94d9eec0087ff824688f4dc276f8fe9742b85c2e20b723ea68fb12c3808",
        792,
    ),
    (
        "push-next-legal-sensitive-v1",
        "1f89f40c81b150def3f42e19304b69585cbe6174dee1bcdd8762d7f01637b48f",
        "96df2bf99249a10c8ca7d28ad15e7025352d5bc89f79c61700efd4550aa1d7e3",
        557,
    ),
    (
        "push-win-draw-loss-v1",
        "f3690d6aa29f83f72b9b3208e6c0a5783a43e2711c5f9a1780a72c6cac3c2e49",
        "2a48252b987d917a51df5a2bfb93da3fa6c2d93768facb27f03226b53c3f3578",
        539,
    ),
    (
        "swap-both-roles-repeat-v1",
        "ac4a2b98eba51c0a0037f65fa52f1c101d5f28cd6824d111d3ff6a721d21b7b6",
        "0d355643eb82555f5ae96394d555814e1ad465331d27f817e4eea647d5af6868",
        456,
    ),
)

ATLAS_SYNTHETIC_SOURCE_ATTESTATION_ROOT_V1 = (
    "586e7d0f4b5a95c396bfdff393cce5c7be176535eb4c5f248e6565445082f95d"
)

ATLAS_SYNTHETIC_UNIQUE_DEFINITION_ROOT_V1 = (
    "72567b0e59c9a76c5d72572955d1d20c0583fb644439dd01d8e5ff2efa53e4af"
)

ATLAS_SYNTHETIC_UNIQUE_D4_ROOT_V1 = (
    "689e5902910b1cc942f4737a012c62735e07057fad3d68ee35514817e4ad901c"
)

ATLAS_SYNTHETIC_PROJECTION_ROOT_V1 = (
    "67658d8b0683ad415f229d4d01a4315aa4ca33f56187c5d0eeecfc8974a70f1f"
)
