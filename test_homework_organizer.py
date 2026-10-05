#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_homework_organizer.py

homework_organizer.py 的标准库单元测试（unittest），无需第三方依赖。

覆盖内容：
    1. classify_file()  各分类与后缀大小写
    2. collect_files()  跳过子文件夹、按后缀过滤
    3. organize_files() dry-run 不改变磁盘、真实移动并自动建目录
    4. 同名文件冲突时自动追加序号，不覆盖已有文件
    5. main() 命令行：dry-run、取消（输入 n）、确认（输入 y）

运行方式：
    python -m unittest -v
    或
    python test_homework_organizer.py
"""

import os
import tempfile
import unittest
from unittest import mock

import homework_organizer as ho


class ClassifyFileTest(unittest.TestCase):
    """测试分类规则 classify_file()。"""

    def test_images(self):
        for name in ("a.jpg", "b.JPEG", "c.png", "d.gif", "e.bmp"):
            self.assertEqual(ho.classify_file(name), "图片", msg=name)

    def test_documents(self):
        for name in ("a.pdf", "b.docx", "c.doc", "d.txt", "e.xlsx"):
            self.assertEqual(ho.classify_file(name), "文档", msg=name)

    def test_videos(self):
        for name in ("a.mp4", "b.mov", "c.avi"):
            self.assertEqual(ho.classify_file(name), "视频", msg=name)

    def test_other_and_no_extension(self):
        for name in ("a.zip", "b.exe", "noext", "archive.tar.gz"):
            self.assertEqual(ho.classify_file(name), "其他", msg=name)

    def test_uppercase_extension(self):
        # 后缀大小写不敏感
        self.assertEqual(ho.classify_file("PHOTO.JPG"), "图片")


class _TempDirMixin:
    """为每个测试用例准备一个独立的临时目录。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def touch(self, name, content="x"):
        """在临时目录下创建一个文件（支持相对子路径）。"""
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        return path


class CollectFilesTest(_TempDirMixin, unittest.TestCase):
    """测试文件扫描 collect_files()。"""

    def test_skips_subdirectories(self):
        self.touch("a.txt")
        os.makedirs(os.path.join(self.dir, "sub"))
        self.touch(os.path.join("sub", "b.txt"))
        names = [f["name"] for f in ho.collect_files(self.dir)]
        self.assertEqual(names, ["a.txt"])

    def test_extension_filter(self):
        self.touch("a.txt")
        self.touch("b.pdf")
        names = [f["name"] for f in ho.collect_files(self.dir, {".pdf"})]
        self.assertEqual(names, ["b.pdf"])


class OrganizeFilesTest(_TempDirMixin, unittest.TestCase):
    """测试归档逻辑 organize_files()。"""

    def test_dry_run_does_not_touch_disk(self):
        self.touch("a.jpg")
        self.touch("b.pdf")
        files = ho.collect_files(self.dir)
        rc = ho.organize_files(self.dir, files, dry_run=True)
        self.assertEqual(rc, 0)
        # 源文件仍在原位
        self.assertTrue(os.path.isfile(os.path.join(self.dir, "a.jpg")))
        self.assertTrue(os.path.isfile(os.path.join(self.dir, "b.pdf")))
        # 不创建任何分类文件夹
        for category in ho.CATEGORY_ORDER:
            self.assertFalse(os.path.isdir(os.path.join(self.dir, category)))

    def test_real_move_creates_folders(self):
        self.touch("a.jpg")
        self.touch("b.pdf")
        self.touch("c.mp4")
        self.touch("d.zip")
        files = ho.collect_files(self.dir)
        rc = ho.organize_files(self.dir, files, dry_run=False)
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.isfile(os.path.join(self.dir, "图片", "a.jpg")))
        self.assertTrue(os.path.isfile(os.path.join(self.dir, "文档", "b.pdf")))
        self.assertTrue(os.path.isfile(os.path.join(self.dir, "视频", "c.mp4")))
        self.assertTrue(os.path.isfile(os.path.join(self.dir, "其他", "d.zip")))
        self.assertFalse(os.path.isfile(os.path.join(self.dir, "a.jpg")))

    def test_name_collision_renamed_not_overwritten(self):
        self.touch("a.txt", content="first")
        ho.organize_files(self.dir, ho.collect_files(self.dir), dry_run=False)
        # 再放入同名文件，第二次归档不应覆盖第一次的
        self.touch("a.txt", content="second")
        ho.organize_files(self.dir, ho.collect_files(self.dir), dry_run=False)
        self.assertTrue(os.path.isfile(os.path.join(self.dir, "文档", "a.txt")))
        self.assertTrue(os.path.isfile(os.path.join(self.dir, "文档", "a_1.txt")))

    def test_empty_directory(self):
        rc = ho.organize_files(self.dir, [], dry_run=False)
        self.assertEqual(rc, 0)


class MainCliTest(_TempDirMixin, unittest.TestCase):
    """测试命令行入口 main()。"""

    def test_organize_dry_run_via_main(self):
        self.touch("a.jpg")
        rc = ho.main([self.dir, "--organize", "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.isfile(os.path.join(self.dir, "a.jpg")))

    def test_cancel_by_user_does_nothing(self):
        self.touch("a.jpg")
        with mock.patch("builtins.input", return_value="n"):
            rc = ho.main([self.dir, "--organize"])
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.isfile(os.path.join(self.dir, "a.jpg")))
        self.assertFalse(os.path.isdir(os.path.join(self.dir, "图片")))

    def test_confirm_by_user_moves_files(self):
        self.touch("a.jpg")
        with mock.patch("builtins.input", return_value="y"):
            rc = ho.main([self.dir, "--organize"])
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.isfile(os.path.join(self.dir, "图片", "a.jpg")))

    def test_nonexistent_path_returns_error(self):
        rc = ho.main([os.path.join(self.dir, "no_such_dir")])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
