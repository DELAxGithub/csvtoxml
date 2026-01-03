#!/usr/bin/env python3
"""
csvtoxml GUI - Drag & Drop CSV to XML Converter
CSVファイルをドラッグ＆ドロップでNLE XMLに変換
"""

import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from csvtoxml.writers.premiere import generate_premiere_xml
from csvtoxml.writers.davinci import generate_davinci_xml


class CsvToXmlApp:
    def __init__(self, root):
        self.root = root
        self.root.title("csvtoxml")
        self.root.geometry("500x520")
        self.root.resizable(False, False)

        # Variables
        self.csv_path = tk.StringVar()
        self.xml_path = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.format_var = tk.StringVar(value="premiere")
        self.gap_seconds = tk.DoubleVar(value=5.0)

        # Default output directory
        self.output_dir.set(str(Path.home() / "Desktop"))

        self._create_widgets()
        self._setup_drag_drop()

    def _create_widgets(self):
        # Main frame with padding
        main = ttk.Frame(self.root, padding="20")
        main.pack(fill=tk.BOTH, expand=True)

        # === CSV File ===
        ttk.Label(main, text="CSV ファイル:").pack(anchor=tk.W)
        csv_frame = ttk.Frame(main)
        csv_frame.pack(fill=tk.X, pady=(0, 10))

        self.csv_entry = ttk.Entry(csv_frame, textvariable=self.csv_path, state="readonly")
        self.csv_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(csv_frame, text="選択...", command=self._browse_csv).pack(side=tk.RIGHT, padx=(5, 0))

        # === Template XML ===
        ttk.Label(main, text="テンプレート XML:").pack(anchor=tk.W)
        xml_frame = ttk.Frame(main)
        xml_frame.pack(fill=tk.X, pady=(0, 10))

        self.xml_entry = ttk.Entry(xml_frame, textvariable=self.xml_path, state="readonly")
        self.xml_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(xml_frame, text="選択...", command=self._browse_xml).pack(side=tk.RIGHT, padx=(5, 0))

        # === Output Directory ===
        ttk.Label(main, text="出力フォルダ:").pack(anchor=tk.W)
        out_frame = ttk.Frame(main)
        out_frame.pack(fill=tk.X, pady=(0, 15))

        self.out_entry = ttk.Entry(out_frame, textvariable=self.output_dir, state="readonly")
        self.out_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(out_frame, text="選択...", command=self._browse_output).pack(side=tk.RIGHT, padx=(5, 0))

        # === Options ===
        options_frame = ttk.LabelFrame(main, text="オプション", padding="10")
        options_frame.pack(fill=tk.X, pady=(0, 15))

        # Format selection
        format_frame = ttk.Frame(options_frame)
        format_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(format_frame, text="出力形式:").pack(side=tk.LEFT)
        ttk.Radiobutton(format_frame, text="Premiere Pro", variable=self.format_var, value="premiere").pack(side=tk.LEFT, padx=(10, 0))
        ttk.Radiobutton(format_frame, text="DaVinci Resolve", variable=self.format_var, value="davinci").pack(side=tk.LEFT, padx=(10, 0))

        # Gap seconds
        gap_frame = ttk.Frame(options_frame)
        gap_frame.pack(fill=tk.X)
        ttk.Label(gap_frame, text="ギャップ秒数:").pack(side=tk.LEFT)
        ttk.Spinbox(gap_frame, from_=0, to=30, increment=0.5, textvariable=self.gap_seconds, width=8).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Label(gap_frame, text="秒").pack(side=tk.LEFT, padx=(5, 0))

        # === Drop Zone ===
        self.drop_zone = tk.Label(
            main,
            text="ここにCSVファイルをドラッグ＆ドロップ\n\nまたは上のボタンでファイルを選択",
            relief=tk.RIDGE,
            bg="#f0f0f0",
            fg="#666666",
            font=("Helvetica", 12),
            height=4
        )
        self.drop_zone.pack(fill=tk.X, pady=(0, 15))

        # === Convert Button ===
        self.convert_btn = ttk.Button(
            main,
            text="変換",
            command=self._convert,
            style="Accent.TButton"
        )
        self.convert_btn.pack(fill=tk.X, ipady=5)

        # Status
        self.status_var = tk.StringVar()
        self.status_label = ttk.Label(main, textvariable=self.status_var, foreground="gray")
        self.status_label.pack(pady=(10, 0))

    def _setup_drag_drop(self):
        """Setup drag and drop functionality"""
        # Basic drop handling via binding
        self.drop_zone.bind("<Button-1>", lambda e: self._browse_csv())

        # For macOS, we need to use tkdnd or handle drops differently
        # Using a simple approach with file dialog for now
        self.root.bind("<Command-o>", lambda e: self._browse_csv())

    def _browse_csv(self):
        path = filedialog.askopenfilename(
            title="CSVファイルを選択",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if path:
            self.csv_path.set(path)
            self._update_drop_zone()

    def _browse_xml(self):
        path = filedialog.askopenfilename(
            title="テンプレートXMLを選択",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")]
        )
        if path:
            self.xml_path.set(path)

    def _browse_output(self):
        path = filedialog.askdirectory(title="出力フォルダを選択")
        if path:
            self.output_dir.set(path)

    def _update_drop_zone(self):
        if self.csv_path.get():
            name = Path(self.csv_path.get()).name
            self.drop_zone.config(
                text=f"選択中: {name}",
                bg="#e8f5e9",
                fg="#2e7d32"
            )

    def _convert(self):
        # Validate inputs
        csv_path = self.csv_path.get()
        xml_path = self.xml_path.get()
        output_dir = self.output_dir.get()

        if not csv_path:
            messagebox.showerror("エラー", "CSVファイルを選択してください")
            return

        if not xml_path:
            messagebox.showerror("エラー", "テンプレートXMLを選択してください")
            return

        if not output_dir:
            messagebox.showerror("エラー", "出力フォルダを選択してください")
            return

        # Generate output path
        csv_name = Path(csv_path).stem
        fmt = self.format_var.get()

        if fmt == "premiere":
            output_file = Path(output_dir) / f"{csv_name}_premiere.xml"
        else:
            output_file = Path(output_dir) / f"{csv_name}_davinci.fcpxml"

        try:
            self.status_var.set("変換中...")
            self.root.update()

            if fmt == "premiere":
                generate_premiere_xml(
                    csv_path=Path(csv_path),
                    template_xml_path=Path(xml_path),
                    output_path=output_file,
                    gap_seconds=self.gap_seconds.get(),
                )
            else:
                generate_davinci_xml(
                    csv_path=Path(csv_path),
                    template_xml_path=Path(xml_path),
                    output_path=output_file,
                    gap_seconds=self.gap_seconds.get(),
                )

            self.status_var.set(f"完了: {output_file.name}")
            messagebox.showinfo("完了", f"XMLを生成しました:\n{output_file}")

        except Exception as e:
            self.status_var.set("エラー")
            messagebox.showerror("エラー", str(e))


def main():
    root = tk.Tk()
    app = CsvToXmlApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
