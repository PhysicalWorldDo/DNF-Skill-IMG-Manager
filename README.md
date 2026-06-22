# DNF 角色技能 IMG 管理器

PySide6 桌面工具，用于查看 `PvfSkillImgDb.dll` 中的角色技能 IMG 数据，并按技能导出关联 IMG 到新的 NPK。

界面使用随包复制的 `data/skill_pages` 技能页数据绘制职业技能图谱，点击技能后在中间栏查看 IMG 资源，在右侧查看大尺寸动画预览。动画默认暂停，手动播放或切帧。

## 开发运行

```powershell
python .\main.py
```

## 打包

```powershell
python .\build_package.py
```

脚本会生成：

- `E:\DNFAutoPlay\DNFtoolall\staged\dnf_skill_img_manager`
- `E:\DNFAutoPlay\DNFtoolall\packages\dnf_skill_img_manager-1.1.1-win-x64.zip`
- `index/tools/dnf_skill_img_manager.json`
- `registry_repo/tools/dnf_skill_img_manager.json`

## NPK 定位规则

IMG 路径使用父目录映射到源 NPK：

```text
sprite/character/archer/effect/centrifugalvenom/bodydeco01.img
=> sprite_character_archer_effect_centrifugalvenom.NPK
```
