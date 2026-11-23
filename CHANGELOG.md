# Changelog

## [0.3.0](https://github.com/freepotato/transparent-sudoku/compare/v0.2.0...v0.3.0) (2026-11-23)


### Features

* adapt pencil layout and size to the number of marks ([a4efda5](https://github.com/freepotato/transparent-sudoku/commit/a4efda5ca1a144a7d379bcaa8bbb9027550852fe))
* add pencil marks, manual checking and cage combinations ([fdff4a5](https://github.com/freepotato/transparent-sudoku/commit/fdff4a570094db8b3b49a13a146de70ead235a75))
* fit combo panel to content and page with the wheel ([cf85fab](https://github.com/freepotato/transparent-sudoku/commit/cf85fab78a342e657e9337d481f3c7d03331faf1))
* keep drafts per selection and clear of cage sums ([18e4cf7](https://github.com/freepotato/transparent-sudoku/commit/18e4cf7384a231275c2b08f618d237d863612323))
* paginate cage combos, dialog-only checks and value undo ([247a259](https://github.com/freepotato/transparent-sudoku/commit/247a2592f1a13201b94fae406984080602d61e9f))
* restore grid lines and dash cage borders ([2204d1e](https://github.com/freepotato/transparent-sudoku/commit/2204d1eb929eafeb3eb1951ff59b81107c8069b3))
* separate grid from cage borders and queue pencil marks ([2e6ae76](https://github.com/freepotato/transparent-sudoku/commit/2e6ae76b4cd40b976ecfdfd8b6280b15f0fece76))
* **ui:** add zoom in/out buttons with clamped cell sizes ([13f6578](https://github.com/freepotato/transparent-sudoku/commit/13f65783e08b99e03b225e0a9a3c45ccfaea3a31))


### Bug Fixes

* **board:** complete cage dashes across block lines and clip around sums ([c920282](https://github.com/freepotato/transparent-sudoku/commit/c920282df9d8c8f3af6a3b4753b95f0d98b3f55c))
* **board:** complete dashed cage borders and punch holes for sums ([85dbd32](https://github.com/freepotato/transparent-sudoku/commit/85dbd325cb29dad37ba62296c260c17a469f2719))
* **board:** draw dashed cage borders on board perimeter too ([0d04794](https://github.com/freepotato/transparent-sudoku/commit/0d0479437bd11ff72f65bbfd7ae98914added800))
* **board:** draw dashed cage borders parallel to the solid cell grid ([15d63b0](https://github.com/freepotato/transparent-sudoku/commit/15d63b0ef20718016049d5bd798b13eaa7f881a2))
* **board:** drop stray cage dashes outside the board perimeter ([65ed183](https://github.com/freepotato/transparent-sudoku/commit/65ed18365b5e2d8e64fe55730890701116e668c9))
* **board:** restore thin cell grid and tier the three line styles ([8fb1de3](https://github.com/freepotato/transparent-sudoku/commit/8fb1de329f2697657eff1e055762662b8a38ce5d))
* **board:** separate dashed cage borders from solid grid lines ([5806a0b](https://github.com/freepotato/transparent-sudoku/commit/5806a0b2a546fcab523769418f013ed8e0e0ebf2))
* **board:** uniform dash-to-solid gap by stroke width and hand-drawn dashes ([f216a36](https://github.com/freepotato/transparent-sudoku/commit/f216a36c86910e697b50a6a1374bf11ba2151125))
* drop page counter from the combo panel ([37e669d](https://github.com/freepotato/transparent-sudoku/commit/37e669d6a2383d9a93b20eed7583b3d0c7f6ab97))
* make the whole title bar draggable ([fac5a05](https://github.com/freepotato/transparent-sudoku/commit/fac5a051a73f15efb524bb47c801c2ca41be96f4))
* retry 5xx gracefully and fall back to cached puzzle ([933bbcc](https://github.com/freepotato/transparent-sudoku/commit/933bbccd60238392536df0c53b9493d424a27c2a))


### Documentation

* cover combo pagination, dialog check and undo ([730064b](https://github.com/freepotato/transparent-sudoku/commit/730064b4317a8aa821c4c100bcb07214352506db))
* document pencil marks, manual check and cage combinations ([e5ace40](https://github.com/freepotato/transparent-sudoku/commit/e5ace40b81b9158dc85f87c7391ce84aa3492bf3))

## [0.2.0](https://github.com/freepotato/transparent-sudoku/compare/v0.1.0...v0.2.0) (2026-11-05)


### Features

* add drag multi-selection with live sum and lighter board lines ([9a497da](https://github.com/freepotato/transparent-sudoku/commit/9a497daf94d6c524934a5866c84834de224085fe))
* sum whole-cage selections and fade the on-screen footprint ([2d86699](https://github.com/freepotato/transparent-sudoku/commit/2d86699bcc5b327957bfddbcdb962c45c23f3ada))


### Documentation

* describe faint outlines, whole-cage sums and stealth defaults ([b5bf64c](https://github.com/freepotato/transparent-sudoku/commit/b5bf64c1d7574b28ae0e00c4831c6724ff0cd50b))
* document drag selection and remove local paths from setup steps ([5c61776](https://github.com/freepotato/transparent-sudoku/commit/5c61776cabfe46dbc25cd5bddd0bfd42f94cf979))

## 0.1.0 (2026-11-05)


### Features

* initial release of Transparent Killer Sudoku ([0448ce9](https://github.com/freepotato/transparent-sudoku/commit/0448ce9497b042049ae2afbb744a797154539131))


### Bug Fixes

* restore today's puzzle lookup through the by_date endpoint ([2ad7f2a](https://github.com/freepotato/transparent-sudoku/commit/2ad7f2aae1714c93d18af541224f4e239946eccf))


### Documentation

* add README with virtual environment setup and usage guide ([0f47333](https://github.com/freepotato/transparent-sudoku/commit/0f47333e0ff7f5de44dddf2ec8a3bd68e8044788))
