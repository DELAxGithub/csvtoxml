/**
 * @fileoverview Google Apps Script to process Premiere Pro transcript CSVs
 * for an XML generation pipeline.
 *
 * This script provides a workflow via a custom menu in Google Sheets:
 * 0. Cleanup all sheets except the currently visible one.
 * 1. Format two raw transcript sheets into the new merged layout.
 * 2. Extract rows that have been manually colored (with styling applied).
 * 3. Generate a final CSV for download, converting NA/empty rows into timed gaps.
 */

// --- グローバル設定 ---

const FORMATTED_SHEET_SUFFIX = '_Formatted_for_XML';
const SELECTED_SHEET_SUFFIX = '_Selected_for_Cut';
const GAP_DURATION_SECONDS = 20;
const FPS = 30;

// Pythonスクリプトは各クリップの前後に149フレームのギャップを追加します。
// 目的のギャップ(20秒=600フレーム)を作るには、ダミークリップの長さを調整します。
// 600フレーム = 149 (前) + ダミークリップ長 + 149 (後)
// => ダミークリップ長 = 600 - 298 = 302 フレーム
const GAP_CLIP_DURATION_FRAMES = (GAP_DURATION_SECONDS * FPS) - (149 * 2);

// 既存のStep3互換のため保持（Step1は別ヘッダーを出力）
const TARGET_HEADERS = ['Speaker Name', 'イン点', 'アウト点', '文字起こし', '色選択'];

// 新しいStep1の出力ヘッダー（ご要望どおりの列構成）
const STEP1_HEADERS = [
  '色選択',           // A
  'イン点',           // B
  'アウト点',         // C
  'スピーカーネーム', // D
  'スピーカーAの文字起こし', // E
  'スピーカーBの文字起こし', // F
  'AやB以外'               // G
];

// Pythonスクリプトで定義されているPremiere Proのラベルカラー
const VALID_COLORS = [
  'Violet', 'Rose', 'Mango', 'Yellow', 'Lavender', 'Caribbean',
  'Tan', 'Forest', 'Blue', 'Purple', 'Teal', 'Brown', 'Gray',
  'Iris', 'Cerulean', 'Magenta'
];

// 色名から薄い背景色への対応表
const COLOR_MAP = {
  'Violet': '#E8D5F2',      // 薄い紫
  'Rose': '#F2D5E8',        // 薄いローズ
  'Mango': '#FFE6CC',       // 薄いマンゴー
  'Yellow': '#FFF2CC',      // 薄い黄色
  'Lavender': '#E6E6FA',    // 薄いラベンダー
  'Caribbean': '#CCF2F2',   // 薄いカリビアン
  'Tan': '#F2E6D9',         // 薄いタン
  'Forest': '#D9F2D9',      // 薄い森色
  'Blue': '#CCE6FF',        // 薄い青
  'Purple': '#E0CCFF',      // 薄い紫
  'Teal': '#CCFFE6',        // 薄いティール
  'Brown': '#E6D9CC',       // 薄い茶色
  'Gray': '#E6E6E6',        // 薄いグレー
  'Iris': '#D9CCFF',        // 薄いアイリス
  'Cerulean': '#CCF2FF',    // 薄いセルリアン
  'Magenta': '#FFCCF2'      // 薄いマゼンタ
};


function getTopSpeakers(data, speakerCol, limit) {
  if (speakerCol === -1 || !Array.isArray(data) || data.length < 2 || limit <= 0) {
    return [];
  }
  const counts = new Map();
  for (let i = 1; i < data.length; i++) {
    const speaker = (data[i][speakerCol] || '').toString().trim();
    if (!speaker) continue;
    counts.set(speaker, (counts.get(speaker) || 0) + 1);
  }
  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(entry => entry[0]);
}

function writeFormattedSheet(ss, formattedSheetName, newData, mainA, mainB) {
  const columnCount = STEP1_HEADERS.length;
  let formattedSheet = ss.getSheetByName(formattedSheetName);
  if (formattedSheet) {
    formattedSheet.clear();
  } else {
    formattedSheet = ss.insertSheet(formattedSheetName);
  }
  ss.setActiveSheet(formattedSheet);

  formattedSheet.getRange(1, 1, newData.length, columnCount).setValues(newData);

  const dataRowCount = Math.max(0, newData.length - 1);
  const colorColumnIndex = STEP1_HEADERS.indexOf('色選択') + 1;
  if (dataRowCount > 0 && colorColumnIndex > 0) {
    const rule = SpreadsheetApp.newDataValidation().requireValueInList(VALID_COLORS, true).build();
    formattedSheet.getRange(2, colorColumnIndex, dataRowCount, 1).setDataValidation(rule);
  }

  formattedSheet.setFrozenRows(1);
  STEP1_HEADERS.forEach((_, i) => formattedSheet.autoResizeColumn(i + 1));

  const colA = STEP1_HEADERS.indexOf('スピーカーAの文字起こし') + 1;
  const colB = STEP1_HEADERS.indexOf('スピーカーBの文字起こし') + 1;
  if (colA > 0) formattedSheet.getRange(1, colA).setNote(mainA ? `A = ${mainA}` : '');
  if (colB > 0) formattedSheet.getRange(1, colB).setNote(mainB ? `B = ${mainB}` : '');

  const rules = [];
  const lastRow = newData.length;
  if (lastRow >= 2) {
    const dRange = formattedSheet.getRange(2, 4, lastRow - 1, 1);
    const eRange = formattedSheet.getRange(2, 5, lastRow - 1, 1);
    const fRange = formattedSheet.getRange(2, 6, lastRow - 1, 1);
    if (mainA) {
      rules.push(
        SpreadsheetApp.newConditionalFormatRule()
          .whenTextEqualTo(mainA)
          .setFontColor('#0B5394')
          .setRanges([dRange])
          .build()
      );
      rules.push(
        SpreadsheetApp.newConditionalFormatRule()
          .whenFormulaSatisfied('=$D2="' + mainA.replace(/"/g, '\"') + '"')
          .setFontColor('#0B5394')
          .setRanges([eRange])
          .build()
      );
    }
    if (mainB) {
      rules.push(
        SpreadsheetApp.newConditionalFormatRule()
          .whenTextEqualTo(mainB)
          .setFontColor('#990000')
          .setRanges([dRange])
          .build()
      );
      rules.push(
        SpreadsheetApp.newConditionalFormatRule()
          .whenFormulaSatisfied('=$D2="' + mainB.replace(/"/g, '\"') + '"')
          .setFontColor('#990000')
          .setRanges([fRange])
          .build()
      );
    }
  }
  formattedSheet.setConditionalFormatRules(rules);

  if (lastRow >= 2) {
    formattedSheet.getRange(2, 5, lastRow - 1, 2).setWrap(true);
  }
  formattedSheet.getRange(1, 1, lastRow, columnCount).setVerticalAlignment('top');
  formattedSheet.getRange(1, 1, lastRow, columnCount).setBorder(true, true, true, true, true, true);

  return formattedSheet;
}


function findHeaderIndex(headers, candidates) {
  if (!Array.isArray(headers) || !headers.length) {
    return -1;
  }
  const normalized = headers.map(h => (h == null ? '' : h.toString().trim().toLowerCase()));
  for (const cand of candidates) {
    const target = (cand || '').toString().trim().toLowerCase();
    if (!target) continue;
    const idx = normalized.indexOf(target);
    if (idx !== -1) {
      return idx;
    }
  }
  return -1;
}


const RAW_HEADER_CANDIDATES = {
  speaker: ['Speaker Name', 'Speaker', 'スピーカー', '話者'],
  start: ['Start Time', 'Start', 'In', 'イン点', 'イン'],
  end: ['End Time', 'End', 'アウト点', 'アウト'],
  text: ['Text', 'Transcript', 'Transcription', '文字起こし', 'テキスト'],
};


/**
 * スプレッドシートを開いたときにカスタムメニューを追加します。
 */
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Premiere XML Helper')
    .addItem('Step 0: 初期化（表示中以外のシートを削除）', 'step0_cleanupOtherSheets')
    .addItem('Step 1A: 2シートをマージして整形', 'step1_formatTranscript')
    .addItem('Step 1B: 単一シートを整形', 'step1_formatSingleTranscript')
    .addItem('Step 2: 色付けした行を抽出', 'step2_extractColoredRows')
    .addItem('Step 3: 最終CSVを生成・ダウンロード', 'step3_generateAndDownloadCsv')
    .addSeparator()
    .addItem('カウント: 選択区間の尺を集計', 'countSelectedDurations')
    .addToUi();
}

/**
 * Step 0: 表示されているシート以外を全削除します（確認ダイアログあり）。
 */
function step0_cleanupOtherSheets() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const active = ss.getActiveSheet();
  const ui = SpreadsheetApp.getUi();
  const response = ui.alert(
    '初期化の確認',
    `現在表示中のシート「${active.getName()}」以外を全て削除します。よろしいですか？`,
    ui.ButtonSet.OK_CANCEL
  );
  if (response !== ui.Button.OK) return;

  const sheets = ss.getSheets();
  let deleted = 0;
  for (const sh of sheets) {
    if (sh.getSheetId() !== active.getSheetId()) {
      ss.deleteSheet(sh);
      deleted++;
    }
  }
  ui.alert(`初期化完了: ${deleted} 件のシートを削除しました。`);
}

/**
 * Step 1: Premiereの生CSVを読み込み、Pythonスクリプトに適した形式に変換して新しいシートに挿入します。
 */
function step1_formatTranscript() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheets = ss.getSheets();
  const sheetNames = sheets.map(s => s.getName());

  // シート選択ダイアログ
  const html = HtmlService.createHtmlOutput(`
    <html>
      <body style="font-family: Arial, sans-serif;">
        <p>マージする2つのシートを選択してください：</p>
        <div style="display:flex; gap:12px; align-items:center;">
          <div>
            <div>シートA（青・スピーカーA）</div>
            <select id="sheetA" style="width: 280px; padding: 6px;">
              ${sheetNames.map(n => `<option value="${n}">${n}</option>`).join('')}
            </select>
          </div>
          <div>
            <div>シートB（赤・スピーカーB）</div>
            <select id="sheetB" style="width: 280px; padding: 6px;">
              ${sheetNames.map(n => `<option value="${n}">${n}</option>`).join('')}
            </select>
          </div>
        </div>
        <br>
        <button onclick="merge()" style="padding:8px 16px;">Step 1 を実行</button>
        <script>
          function merge(){
            const a = document.getElementById('sheetA').value;
            const b = document.getElementById('sheetB').value;
            if(!a || !b){ alert('2つのシートを選択してください'); return; }
            if(a === b){ alert('別々のシートを選んでください'); return; }
            google.script.run
              .withSuccessHandler(google.script.host.close)
              .withFailureHandler(err => alert('エラー: ' + err))
              .step1_processTwoSheets(a, b);
          }
        </script>
      </body>
    </html>
  `).setWidth(620).setHeight(200);

  SpreadsheetApp.getUi().showModalDialog(html, 'Step 1: 2シートをマージ');
}

function timecodeToFrames(tc, fps) {
  if (!tc) return 0;
  const parts = tc.toString().replace(/;/g, ':').split(':');
  let h=0,m=0,s=0,f=0;
  if (parts.length === 4){ [h,m,s,f] = parts.map(x => parseInt(x, 10) || 0); }
  else if (parts.length === 3){ [m,s,f] = parts.map(x => parseInt(x, 10) || 0); }
  else if (parts.length === 2){ [s,f] = parts.map(x => parseInt(x, 10) || 0); }
  return ((h*3600 + m*60 + s) * fps) + f;
}

function step1_processTwoSheets(sheetAName, sheetBName) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheetA = ss.getSheetByName(sheetAName);
  const sheetB = ss.getSheetByName(sheetBName);
  if (!sheetA || !sheetB){ throw new Error('選択したシートが見つかりません'); }

  const dataA = sheetA.getDataRange().getValues();
  const dataB = sheetB.getDataRange().getValues();
  if (dataA.length < 2 || dataB.length < 2){ throw new Error('どちらかのシートが空か、ヘッダーしかありません'); }

  const headersA = dataA[0];
  const headersB = dataB[0];
  const speakerColA = findHeaderIndex(headersA, RAW_HEADER_CANDIDATES.speaker);
  const startColA = findHeaderIndex(headersA, RAW_HEADER_CANDIDATES.start);
  const endColA = findHeaderIndex(headersA, RAW_HEADER_CANDIDATES.end);
  const textColA = findHeaderIndex(headersA, RAW_HEADER_CANDIDATES.text);
  const speakerColB = findHeaderIndex(headersB, RAW_HEADER_CANDIDATES.speaker);
  const startColB = findHeaderIndex(headersB, RAW_HEADER_CANDIDATES.start);
  const endColB = findHeaderIndex(headersB, RAW_HEADER_CANDIDATES.end);
  const textColB = findHeaderIndex(headersB, RAW_HEADER_CANDIDATES.text);
  if ([speakerColA,startColA,endColA,textColA,speakerColB,startColB,endColB,textColB].includes(-1)){
    throw new Error('必要なヘッダー("Speaker Name","Start Time","End Time","Text")が見つかりません');
  }

  // 各シートで最頻出のスピーカー = メインスピーカー
  const mainA = getTopSpeakers(dataA, speakerColA, 1)[0] || '';
  const mainB = getTopSpeakers(dataB, speakerColB, 1)[0] || '';

  // マージしてイン点でソート
  const merged = [];
  for (let i=1;i<dataA.length;i++){
    const r = dataA[i];
    merged.push({
      origin:'A',
      in:r[startColA]?.toString().replace(/;/g, ':'),
      out:r[endColA]?.toString().replace(/;/g, ':'),
      sp:(r[speakerColA]||'').toString(),
      text:(r[textColA]||'').toString()
    });
  }
  for (let i=1;i<dataB.length;i++){
    const r = dataB[i];
    merged.push({
      origin:'B',
      in:r[startColB]?.toString().replace(/;/g, ':'),
      out:r[endColB]?.toString().replace(/;/g, ':'),
      sp:(r[speakerColB]||'').toString(),
      text:(r[textColB]||'').toString()
    });
  }
  merged.sort((x,y)=> timecodeToFrames(x.in, FPS) - timecodeToFrames(y.in, FPS));

  const newData = [STEP1_HEADERS];
  merged.forEach(item => {
    const row = Array(STEP1_HEADERS.length).fill('');
    row[STEP1_HEADERS.indexOf('色選択')] = '';
    row[STEP1_HEADERS.indexOf('イン点')] = item.in;
    row[STEP1_HEADERS.indexOf('アウト点')] = item.out;
    row[STEP1_HEADERS.indexOf('スピーカーネーム')] = item.sp;
    if (item.origin === 'A'){
      if (mainA && item.sp === mainA){
        row[STEP1_HEADERS.indexOf('スピーカーAの文字起こし')] = item.text;
      } else {
        row[STEP1_HEADERS.indexOf('AやB以外')] = item.text;
      }
    } else {
      if (mainB && item.sp === mainB){
        row[STEP1_HEADERS.indexOf('スピーカーBの文字起こし')] = item.text;
      } else {
        row[STEP1_HEADERS.indexOf('AやB以外')] = item.text;
      }
    }
    newData.push(row);
  });

  const formattedSheetName = sheetA.getName() + '_AND_' + sheetB.getName() + FORMATTED_SHEET_SUFFIX;
  writeFormattedSheet(ss, formattedSheetName, newData, mainA, mainB);

  SpreadsheetApp.getUi().alert(`Step 1A 完了。 "${formattedSheetName}" を作成しました。\n\nA(青): ${mainA || '-'} / B(赤): ${mainB || '-'}`);
}

function step1_formatSingleTranscript() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheets = ss.getSheets();
  const candidates = sheets.filter(sheet => {
    const name = sheet.getName();
    return !name.endsWith(FORMATTED_SHEET_SUFFIX) && !name.endsWith(SELECTED_SHEET_SUFFIX);
  });

  if (candidates.length === 0) {
    SpreadsheetApp.getUi().alert('整形可能なシートが見つかりませんでした。');
    return;
  }

  if (candidates.length === 1) {
    step1_processSingleSheet(candidates[0].getName());
    return;
  }

  const sheetOptions = candidates.map(sheet => sheet.getName());
  const html = HtmlService.createHtmlOutput(`
    <html>
      <body style="font-family: Arial, sans-serif;">
        <p>整形するシートを選択してください：</p>
        <select id="sheetSingle" style="width: 300px; padding: 6px;">
          ${sheetOptions.map(n => `<option value="${n}">${n}</option>`).join('')}
        </select>
        <br><br>
        <button onclick="formatSingle()" style="padding:8px 16px;">Step 1B を実行</button>
        <script>
          function formatSingle(){
            const name = document.getElementById('sheetSingle').value;
            if(!name){ alert('シートを選択してください'); return; }
            google.script.run
              .withSuccessHandler(google.script.host.close)
              .withFailureHandler(err => alert('エラー: ' + err))
              .step1_processSingleSheet(name);
          }
        </script>
      </body>
    </html>
  `).setWidth(360).setHeight(160);

  SpreadsheetApp.getUi().showModalDialog(html, 'Step 1B: 単一シートを整形');
}

function step1_processSingleSheet(sheetName) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(sheetName);

  if (!sheet) {
    SpreadsheetApp.getUi().alert(`シート "${sheetName}" が見つかりません。`);
    return;
  }

  const data = sheet.getDataRange().getValues();
  if (data.length < 2) {
    throw new Error('選択したシートにデータ行がありません');
  }

  const headers = data[0];
  const speakerCol = findHeaderIndex(headers, RAW_HEADER_CANDIDATES.speaker);
  const startCol = findHeaderIndex(headers, RAW_HEADER_CANDIDATES.start);
  const endCol = findHeaderIndex(headers, RAW_HEADER_CANDIDATES.end);
  const textCol = findHeaderIndex(headers, RAW_HEADER_CANDIDATES.text);
  if ([speakerCol, startCol, endCol, textCol].includes(-1)) {
    throw new Error('必要なヘッダー("Speaker Name","Start Time","End Time","Text")が見つかりません');
  }

  const topSpeakers = getTopSpeakers(data, speakerCol, 2);
  const mainA = topSpeakers[0] || '';
  const mainB = topSpeakers[1] || '';

  const newData = [STEP1_HEADERS];
  for (let i = 1; i < data.length; i++) {
    const r = data[i];
    const row = Array(STEP1_HEADERS.length).fill('');
    row[STEP1_HEADERS.indexOf('色選択')] = '';
    row[STEP1_HEADERS.indexOf('イン点')] = (r[startCol] || '').toString().replace(/;/g, ':');
    row[STEP1_HEADERS.indexOf('アウト点')] = (r[endCol] || '').toString().replace(/;/g, ':');
    const speaker = (r[speakerCol] || '').toString();
    row[STEP1_HEADERS.indexOf('スピーカーネーム')] = speaker;
    const text = (r[textCol] || '').toString();
    if (mainA && speaker === mainA) {
      row[STEP1_HEADERS.indexOf('スピーカーAの文字起こし')] = text;
    } else if (mainB && speaker === mainB) {
      row[STEP1_HEADERS.indexOf('スピーカーBの文字起こし')] = text;
    } else {
      row[STEP1_HEADERS.indexOf('AやB以外')] = text;
    }
    newData.push(row);
  }

  const formattedSheetName = sheet.getName() + FORMATTED_SHEET_SUFFIX;
  writeFormattedSheet(ss, formattedSheetName, newData, mainA, mainB);

  SpreadsheetApp.getUi().alert(`Step 1B 完了。 "${formattedSheetName}" を作成しました。\n\nA(青): ${mainA || '-'} / B(赤): ${mainB || '-'}`);
}

/**
 * Step 2: "Formatted"シートから色が割り当てられた行を抽出し、並べ替え用の新しい"Selected"シートにコピーします。
 */
function step2_extractColoredRows() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  
  // Formatted シートを探す（接尾辞で終わるシート名を検索）
  const sheets = ss.getSheets();
  const formattedSheets = sheets.filter(sheet => sheet.getName().endsWith(FORMATTED_SHEET_SUFFIX));

  if (formattedSheets.length === 0) {
    SpreadsheetApp.getUi().alert(`"${FORMATTED_SHEET_SUFFIX}" で終わるシートが見つかりません。Step 1を先に実行してください。`);
    return;
  }

  let formattedSheet;
  if (formattedSheets.length === 1) {
    formattedSheet = formattedSheets[0];
  } else {
    // 複数のFormattedシートがある場合、選択ダイアログを表示
    const ui = SpreadsheetApp.getUi();
    const sheetNames = formattedSheets.map(sheet => sheet.getName());
    ui.showModalDialog(
      HtmlService.createHtmlOutput(`
        <html>
          <body>
            <p>処理するFormattedシートを選択してください：</p>
            <select id="sheetSelect" style="width: 300px; padding: 5px;">
              ${sheetNames.map(name => `<option value="${name}">${name}</option>`).join('')}
            </select>
            <br><br>
            <button onclick="selectSheet()" style="padding: 8px 16px;">選択</button>
            <script>
              function selectSheet() {
                const select = document.getElementById('sheetSelect');
                google.script.run
                  .withSuccessHandler(google.script.host.close)
                  .withFailureHandler((error) => alert('エラー: ' + error))
                  .step2_processSelectedSheet(select.value);
              }
            </script>
          </body>
        </html>
      `).setWidth(400).setHeight(200),
      '処理するシートを選択'
    );
    return; // ダイアログ処理後にstep2_processSelectedSheetが呼ばれる
  }

  // 単一シートの場合は直接処理
  step2_processSelectedSheet(formattedSheet.getName());
}

/**
 * Step 2の実際の処理を行う関数（シート選択後に呼ばれる）
 */
function step2_processSelectedSheet(formattedSheetName) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const formattedSheet = ss.getSheetByName(formattedSheetName);

  if (!formattedSheet) {
    SpreadsheetApp.getUi().alert(`シート "${formattedSheetName}" が見つかりません。`);
    return;
  }

  const data = formattedSheet.getDataRange().getValues();
  const headers = data[0];
  const colorColumnIndex = headers.indexOf('色選択');
  const speakerNameIndex = (() => {
    const jp = headers.indexOf('スピーカーネーム');
    if (jp !== -1) return jp;
    return headers.indexOf('Speaker Name');
  })();

  if (colorColumnIndex === -1) {
    SpreadsheetApp.getUi().alert(`"${formattedSheet.getName()}" シートに "色選択" 列が見つかりません。`);
    return;
  }

  const coloredRows = data.slice(1).filter(row => row[colorColumnIndex].toString().trim() !== '');

  if (coloredRows.length === 0) {
    SpreadsheetApp.getUi().alert(`"${formattedSheet.getName()}" シートに色が付けられた行が見つかりませんでした。`);
    return;
  }

  // 元シートの列インデックスを取得
  const inCol = headers.indexOf('イン点');
  const outCol = headers.indexOf('アウト点');
  const textColA = headers.indexOf('スピーカーAの文字起こし');
  const textColB = headers.indexOf('スピーカーBの文字起こし');
  const textColOther = headers.indexOf('AやB以外');
  const legacyTextCol = headers.indexOf('文字起こし');

  // 新しい出力列インデックス
  const speakerOutIdx = TARGET_HEADERS.indexOf('Speaker Name');
  const inOutIdx = TARGET_HEADERS.indexOf('イン点');
  const outOutIdx = TARGET_HEADERS.indexOf('アウト点');
  const textOutIdx = TARGET_HEADERS.indexOf('文字起こし');
  const colorOutIdx = TARGET_HEADERS.indexOf('色選択');

  const buildTextValue = (row) => {
    const candidates = [textColA, textColB, textColOther, legacyTextCol]
      .filter(idx => idx !== -1)
      .map(idx => row[idx]);
    for (const val of candidates) {
      if (val != null && val.toString().trim() !== '') {
        return val.toString();
      }
    }
    return '';
  };

  const selectedRows = [];
  let naCounter = 1;

  for (let i = 0; i < coloredRows.length; i++) {
    const current = coloredRows[i];
    const outRow = Array(TARGET_HEADERS.length).fill('');
    if (speakerOutIdx !== -1) {
      const sp = speakerNameIndex !== -1 ? current[speakerNameIndex] : '';
      outRow[speakerOutIdx] = sp != null ? sp.toString() : '';
    }
    if (inOutIdx !== -1) {
      const val = inCol !== -1 ? current[inCol] : '';
      outRow[inOutIdx] = val != null ? val.toString() : '';
    }
    if (outOutIdx !== -1) {
      const val = outCol !== -1 ? current[outCol] : '';
      outRow[outOutIdx] = val != null ? val.toString() : '';
    }
    if (textOutIdx !== -1) {
      outRow[textOutIdx] = buildTextValue(current);
    }
    if (colorOutIdx !== -1) {
      const raw = current[colorColumnIndex];
      outRow[colorOutIdx] = raw != null ? raw.toString().trim() : '';
    }

    const colorForRow = colorOutIdx !== -1 ? outRow[colorOutIdx] : '';
    selectedRows.push({ values: outRow, color: colorForRow || '', isNa: false });

    if (i < coloredRows.length - 1) {
      const currentColor = (current[colorColumnIndex] || '').toString().trim();
      const nextColor = (coloredRows[i + 1][colorColumnIndex] || '').toString().trim();
      if (currentColor !== nextColor) {
        const naRow = Array(TARGET_HEADERS.length).fill('');
        if (speakerOutIdx !== -1) {
          naRow[speakerOutIdx] = `NA${naCounter}`;
        }
        selectedRows.push({ values: naRow, color: '', isNa: true });
        naCounter++;
      }
    }
  }

  const selectedData = [TARGET_HEADERS].concat(selectedRows.map(r => r.values));

  const baseSheetName = formattedSheet.getName().replace(FORMATTED_SHEET_SUFFIX, '');
  const selectedSheetName = baseSheetName + SELECTED_SHEET_SUFFIX;
  
  let selectedSheet = ss.getSheetByName(selectedSheetName);
  if (selectedSheet) {
    selectedSheet.clear();
  } else {
    selectedSheet = ss.insertSheet(selectedSheetName);
  }
  ss.setActiveSheet(selectedSheet);

  selectedSheet.getRange(1, 1, selectedData.length, TARGET_HEADERS.length).setValues(selectedData);
  TARGET_HEADERS.forEach((_, i) => selectedSheet.autoResizeColumn(i + 1));
  selectedSheet.setFrozenRows(1);

  // 色選択列のプルダウンを設定
  if (colorOutIdx !== -1) {
    const rule = SpreadsheetApp.newDataValidation().requireValueInList(VALID_COLORS, true).build();
    selectedSheet
      .getRange(2, colorOutIdx + 1, Math.max(0, selectedData.length - 1), 1)
      .setDataValidation(rule);
  }

  // Step 4 相当の色塗り（E/F/G列の背景色）と体裁（幅/折返し/上寄せ/罫線）を適用
  try {
    const numRows = selectedData.length;
    if (numRows > 1) {
      const selColorCol = TARGET_HEADERS.indexOf('色選択');
      const textIdx = TARGET_HEADERS.indexOf('文字起こし');
      const speakerOutCol = TARGET_HEADERS.indexOf('Speaker Name');
      // Step1で付与したメイン話者メモ（A/B）から名前を取得（なければ頻度で推定）
      let mainA = '';
      let mainB = '';
      try {
        const eIdx = headers.indexOf('スピーカーAの文字起こし');
        const fIdx = headers.indexOf('スピーカーBの文字起こし');
        if (eIdx !== -1) {
          const noteA = formattedSheet.getRange(1, eIdx + 1).getNote();
          if (noteA) {
            const m = noteA.match(/A\s*=\s*(.*)/);
            if (m) mainA = m[1];
          }
        }
        if (fIdx !== -1) {
          const noteB = formattedSheet.getRange(1, fIdx + 1).getNote();
          if (noteB) {
            const m = noteB.match(/B\s*=\s*(.*)/);
            if (m) mainB = m[1];
          }
        }
      } catch (e) {}
      if (!mainA || !mainB) {
        // フォールバック: D列の頻度上位2名
        const counts = new Map();
        for (let i = 1; i < data.length; i++) {
          const sp = (data[i][speakerNameIndex] || '').toString().trim();
          if (!sp) continue;
          counts.set(sp, (counts.get(sp) || 0) + 1);
        }
        const arr = Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
        if (!mainA && arr[0]) mainA = arr[0][0];
        if (!mainB && arr[1]) mainB = arr[1][0];
      }

      if (selColorCol !== -1 && textIdx !== -1) {
        const colorVals = selectedSheet
          .getRange(2, selColorCol + 1, numRows - 1, 1)
          .getValues()
          .map(r => (r[0] || '').toString().trim());

        const colorFor = (label) => (label && COLOR_MAP[label]) ? COLOR_MAP[label] : null;
        const fillColors = colorVals.map(v => [colorFor(v)]);
        selectedSheet.getRange(2, textIdx + 1, numRows - 1, 1).setBackgrounds(fillColors);
      }

      if (textIdx !== -1) {
        selectedSheet.getRange(2, textIdx + 1, numRows - 1, 1).setWrap(true);
        selectedSheet.setColumnWidth(textIdx + 1, Math.round(50 * 7));
        selectedSheet.getRange(1, textIdx + 1, numRows, 1).setWrap(true);
      }

      // 全セル上寄せ
      selectedSheet.getRange(1, 1, numRows, TARGET_HEADERS.length).setVerticalAlignment('top');

      // 罫線（黒・最小幅）
      selectedSheet
        .getRange(1, 1, numRows, TARGET_HEADERS.length)
        .setBorder(true, true, true, true, true, true, '#000000', SpreadsheetApp.BorderStyle.SOLID);

      // D列（スピーカーネーム）の文字色も引き継ぎ（条件付き書式を再設定）
      try {
        const rules = selectedSheet.getConditionalFormatRules();
        const dRange = selectedSheet.getRange(2, speakerOutCol + 1, Math.max(0, numRows - 1), 1);
        if (mainA) {
          rules.push(
            SpreadsheetApp.newConditionalFormatRule()
              .whenTextEqualTo(mainA)
              .setFontColor('#0B5394') // 青
              .setRanges([dRange])
              .build()
          );
        }
        if (mainB) {
          rules.push(
            SpreadsheetApp.newConditionalFormatRule()
              .whenTextEqualTo(mainB)
              .setFontColor('#990000') // 赤
              .setRanges([dRange])
              .build()
          );
        }
        selectedSheet.setConditionalFormatRules(rules);
      } catch (e) {}

      // NA行を薄いグレーで塗りつぶし
      try {
        if (speakerOutCol !== -1) {
          const names = selectedSheet.getRange(2, speakerOutCol + 1, numRows - 1, 1).getValues();
          for (let i = 0; i < names.length; i++) {
            const val = (names[i][0] || '').toString().trim();
            if (/^NA\d+$/i.test(val)) {
              selectedSheet.getRange(i + 2, 1, 1, TARGET_HEADERS.length).setBackground('#EDEDED');
            }
          }
        }
      } catch (e) {}
    }
  } catch (e) {
    // 装飾エラーは無視（データは作成済み）
  }

  SpreadsheetApp.getUi().alert(`Step 2 完了。 "${selectedSheetName}" を作成しました（色塗り・罫線・整形を適用済み）。`);
}

/**
 * フレーム数を HH:MM:SS:FF 形式のタイムコードに変換します。
 * @param {number} totalFrames - 総フレーム数
 * @param {number} fps - フレームレート
 * @return {string} タイムコード文字列
 */
function framesToTimecode(totalFrames, fps) {
  const totalSeconds = Math.floor(totalFrames / fps);
  const frames = totalFrames % fps;
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const pad = (num) => num.toString().padStart(2, '0');
  return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}:${pad(frames)}`;
}

/**
 * Step 3: "Selected"シートを読み込み、空行をギャップに変換して、最終的なCSVのダウンロードリンクを生成します。
 */
function step3_generateAndDownloadCsv() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  
  // Selected シートを探す（接尾辞で終わるシート名を検索）
  const sheets = ss.getSheets();
  const selectedSheets = sheets.filter(sheet => sheet.getName().endsWith(SELECTED_SHEET_SUFFIX));

  if (selectedSheets.length === 0) {
    SpreadsheetApp.getUi().alert(`"${SELECTED_SHEET_SUFFIX}" で終わるシートが見つかりません。Step 2を先に実行してください。`);
    return;
  }

  let selectedSheet;
  if (selectedSheets.length === 1) {
    selectedSheet = selectedSheets[0];
  } else {
    // 複数のSelectedシートがある場合、選択ダイアログを表示
    const ui = SpreadsheetApp.getUi();
    const sheetNames = selectedSheets.map(sheet => sheet.getName());
    ui.showModalDialog(
      HtmlService.createHtmlOutput(`
        <html>
          <body>
            <p>CSV生成するSelectedシートを選択してください：</p>
            <select id="sheetSelect" style="width: 300px; padding: 5px;">
              ${sheetNames.map(name => `<option value="${name}">${name}</option>`).join('')}
            </select>
            <br><br>
            <button onclick="selectSheet()" style="padding: 8px 16px;">選択</button>
            <script>
              function selectSheet() {
                const select = document.getElementById('sheetSelect');
                google.script.run
                  .withSuccessHandler(google.script.host.close)
                  .withFailureHandler((error) => alert('エラー: ' + error))
                  .step3_processSelectedSheet(select.value);
              }
            </script>
          </body>
        </html>
      `).setWidth(400).setHeight(200),
      'CSV生成するシートを選択'
    );
    return; // ダイアログ処理後にstep3_processSelectedSheetが呼ばれる
  }

  // 単一シートの場合は直接処理
  step3_processSelectedSheet(selectedSheet.getName());
}

/**
 * Step 3の実際の処理を行う関数（シート選択後に呼ばれる）
 */
function step3_processSelectedSheet(selectedSheetName) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const selectedSheet = ss.getSheetByName(selectedSheetName);

  if (!selectedSheet) {
    SpreadsheetApp.getUi().alert(`シート "${selectedSheetName}" が見つかりません。`);
    return;
  }

  const data = selectedSheet.getDataRange().getValues();
  const headers = data[0] || [];

  // 列インデックス（新旧両対応）
  const colorCol = headers.indexOf('色選択');
  const inCol = headers.indexOf('イン点') !== -1 ? headers.indexOf('イン点') : headers.indexOf('Start Time');
  const outCol = headers.indexOf('アウト点') !== -1 ? headers.indexOf('アウト点') : headers.indexOf('End Time');
  const speakerCol = (() => {
    const jp = headers.indexOf('スピーカーネーム');
    if (jp !== -1) return jp;
    return headers.indexOf('Speaker Name');
  })();
  const textColOld = headers.indexOf('文字起こし');
  const textColA = headers.indexOf('スピーカーAの文字起こし');
  const textColB = headers.indexOf('スピーカーBの文字起こし');
  const textColOther = headers.indexOf('AやB以外');

  const finalCsvRows = [TARGET_HEADERS];
  let gapCounter = 0;
  const gapOutTimecode = framesToTimecode(GAP_CLIP_DURATION_FRAMES, FPS);

  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    const allBlank = row.every(cell => cell.toString().trim() === '');
    // NA行 or 完全空行 → ギャップ行として出力
    const speakerVal = speakerCol !== -1 ? (row[speakerCol] || '').toString().trim() : '';
    const isNA = /^NA\d+$/i.test(speakerVal);
    if (allBlank || isNA) {
      gapCounter++;
      const gapRow = Array(TARGET_HEADERS.length).fill('');
      gapRow[TARGET_HEADERS.indexOf('イン点')] = '00:00:00:00';
      gapRow[TARGET_HEADERS.indexOf('アウト点')] = gapOutTimecode;
      // テロップ本文はE列（スピーカーAの文字起こし）優先で拾う
      let telopText = '';
      if (textColA !== -1 && row[textColA]) telopText = row[textColA].toString();
      else if (textColB !== -1 && row[textColB]) telopText = row[textColB].toString();
      else if (textColOther !== -1 && row[textColOther]) telopText = row[textColOther].toString();
      gapRow[TARGET_HEADERS.indexOf('文字起こし')] = telopText || `--- ${GAP_DURATION_SECONDS}s GAP ---`;
      gapRow[TARGET_HEADERS.indexOf('色選択')] = `GAP_${gapCounter}`;
      finalCsvRows.push(gapRow);
      continue;
    }

    // 時間と色がある行のみを最終CSVに含める
    const inTc = inCol !== -1 ? (row[inCol] || '').toString().replace(/;/g, ':') : '';
    const outTc = outCol !== -1 ? (row[outCol] || '').toString().replace(/;/g, ':') : '';
    const colorVal = colorCol !== -1 ? (row[colorCol] || '').toString().trim() : '';
    if (!inTc || !outTc) {
      // 時間がない行（例: NA行）はスキップ
      continue;
    }

    // テキストは E>F>G>旧"文字起こし" の優先で採用
    let textVal = '';
    if (textColA !== -1 && row[textColA]) textVal = row[textColA].toString();
    else if (textColB !== -1 && row[textColB]) textVal = row[textColB].toString();
    else if (textColOther !== -1 && row[textColOther]) textVal = row[textColOther].toString();
    else if (textColOld !== -1 && row[textColOld]) textVal = row[textColOld].toString();

    const outRow = Array(TARGET_HEADERS.length).fill('');
    outRow[TARGET_HEADERS.indexOf('Speaker Name')] = speakerCol !== -1 ? (row[speakerCol] || '').toString() : '';
    outRow[TARGET_HEADERS.indexOf('イン点')] = inTc;
    outRow[TARGET_HEADERS.indexOf('アウト点')] = outTc;
    outRow[TARGET_HEADERS.indexOf('文字起こし')] = textVal;
    outRow[TARGET_HEADERS.indexOf('色選択')] = colorVal;
    finalCsvRows.push(outRow);
  }

  const csvContent = finalCsvRows
    .map(row => row.map(cell => {
      let cellStr = (cell == null ? '' : cell).toString();
      if (/[",\n]/.test(cellStr)) {
        cellStr = '"' + cellStr.replace(/"/g, '""') + '"';
      }
      return cellStr;
    }).join(','))
    .join('\n');

  // ダウンロードファイル名: 対象シート名の冒頭5文字 + .csv（例: 022_2.csv）
  const shortName = (selectedSheetName || 'output').toString().slice(0, 5).replace(/[^\w\-\.]/g, '_');
  const fileName = `${shortName}.csv`;
  const html = `<html><body><p>CSVの生成が完了しました。下のリンクをクリックしてダウンロードしてください。</p><a href="data:text/csv;charset=utf-8,${encodeURIComponent(csvContent)}" download="${fileName}">Download ${fileName}</a></body></html>`;
  SpreadsheetApp.getUi().showModalDialog(HtmlService.createHtmlOutput(html).setWidth(400).setHeight(150), 'CSVをダウンロード');
}

/**
 * 色選択列をフラグとして区間ごとの尺と総尺を集計します。
 */
function countSelectedDurations() {
  const ui = SpreadsheetApp.getUi();
  const sheet = SpreadsheetApp.getActiveSheet();
  const data = sheet.getDataRange().getValues();

  if (data.length <= 1) {
    ui.alert('データ行が存在しません。');
    return;
  }

  const headers = data[0];
  const colorCol = headers.indexOf('色選択');
  const inCol = headers.indexOf('イン点');
  const outCol = headers.indexOf('アウト点');

  if (colorCol === -1 || inCol === -1 || outCol === -1) {
    ui.alert('色選択/イン点/アウト点の列が見つかりません。対象シートを確認してください。');
    return;
  }

  const durationCol = colorCol + 1; // F列想定
  const summaryCol = durationCol + 1; // G列想定
  const durationValues = Array.from({ length: data.length - 1 }, () => ['']);

  let totalFrames = 0;
  let segmentCount = 0;
  let currentStartRow = null;
  let currentColor = null;
  let firstInFrames = null;
  let lastOutFrames = null;

  const flushSegment = () => {
    if (currentStartRow == null || firstInFrames == null || lastOutFrames == null) {
      currentStartRow = null;
      firstInFrames = null;
      lastOutFrames = null;
      currentColor = null;
      return;
    }
    const durationFrames = Math.max(0, lastOutFrames - firstInFrames);
    const durationTc = framesToTimecode(durationFrames, FPS);
    durationValues[currentStartRow - 1][0] = durationTc;
    totalFrames += durationFrames;
    segmentCount += 1;
    currentStartRow = null;
    currentColor = null;
    firstInFrames = null;
    lastOutFrames = null;
  };

  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    const colorVal = (row[colorCol] || '').toString().trim();
    const flagged = colorVal !== '' && !/^GAP_/i.test(colorVal);

    if (!flagged) {
      flushSegment();
      continue;
    }

    const inTc = (row[inCol] || '').toString();
    const outTc = (row[outCol] || '').toString();
    if (!inTc || !outTc) {
      flushSegment();
      continue;
    }

    const inFrames = timecodeToFrames(inTc, FPS);
    const outFrames = timecodeToFrames(outTc, FPS);

    if (currentStartRow == null) {
      currentStartRow = i;
      currentColor = colorVal;
      firstInFrames = inFrames;
      lastOutFrames = outFrames;
      continue;
    }

    if (currentColor !== colorVal) {
      flushSegment();
      currentStartRow = i;
      currentColor = colorVal;
      firstInFrames = inFrames;
      lastOutFrames = outFrames;
      continue;
    }

    lastOutFrames = outFrames;
  }

  flushSegment();

  if (data.length - 1 > 0) {
    sheet.getRange(2, durationCol + 1, data.length - 1, 1).setValues(durationValues);
  }
  sheet.getRange(1, durationCol + 1).setValue('区間デュレーション');

  const totalTc = framesToTimecode(totalFrames, FPS);
  sheet.getRange(1, summaryCol + 1).setValue(`総尺: ${totalTc}`);

  ui.alert(`カウント完了: 区間 ${segmentCount} 件、総尺 ${totalTc}`);
}

/**
 * Step 4: 色選択の値に基づいてD列（文字起こし）のセルを薄い色で塗りつぶします。
 */
// Step 4 は Step 2 に統合済みのため削除しました。
