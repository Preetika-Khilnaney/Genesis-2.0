/* The collection: one consistent card per format, rendered from data, with filter tabs.
   Undetected-damage rates are the measured results of tools/benchmark.py (docs/EVALUATION.md). */
import { paint } from './pixel.js';

const FORMATS = [
  { name: 'LIBRA-98', group: 'rev', icon: 'floppy', origin: 'Library circulation PC · 1998',
    recovers: 'Book records: title, author, year, copies, due date',
    check: 'Per-record sum + file sum', kind: 'checksum', samples: 4, silent: 0.00 },
  { name: 'LABLOG', group: 'rev', icon: 'crt', origin: 'Lab data logger · early 1990s',
    recovers: 'Timed instrument readings with units and events',
    check: 'CRC-16 on every block', kind: 'checksum', samples: 3, silent: 0.00 },
  { name: 'VAULT', group: 'rev', icon: 'crate', origin: 'School office archive utility',
    recovers: 'Stored notes, scans and binary files',
    check: 'CRC-32 on every stored file', kind: 'checksum', samples: 3, silent: 1.21 },
  { name: 'WKS', group: 'doc', icon: 'sheet', origin: 'Lotus 1-2-3 · DOS · early 1990s',
    recovers: 'Cells, formulas and number formats',
    check: 'Formula results recomputed', kind: 'value', samples: 3, silent: 13.40 },
  { name: 'WPD', group: 'doc', icon: 'doc', origin: 'WordPerfect 5 · government office',
    recovers: 'Paragraphs, page breaks, summary',
    check: 'Formatting codes and text checked', kind: 'value', samples: 2, silent: 28.05 },
  { name: 'BRAVO', group: 'doc', icon: 'doc', origin: 'Research-lab editor · 1970s',
    recovers: 'Paragraphs and bold/italic runs',
    check: 'Text and format-run lengths', kind: 'structure', samples: 2, silent: 30.67 },
  { name: 'CVT', group: 'doc', icon: 'cartridge', origin: 'Commodore 64 GEOS conversion',
    recovers: 'File info and text records',
    check: 'Block count and text checked', kind: 'value', samples: 2, silent: 21.69 },
  { name: 'EBCDIC-DUMP', group: 'arc', icon: 'reel', origin: 'University mainframe tape · 1999',
    recovers: 'Student records with packed decimals',
    check: 'Trailer count and totals', kind: 'checksum', samples: 3, silent: 15.19 },
  { name: 'WAD', group: 'arc', icon: 'cassette', origin: '1990s shooter game data',
    recovers: 'Directory of named data lumps',
    check: 'Directory and data tiling', kind: 'structure', samples: 1, silent: 34.81 },
  { name: 'PAK', group: 'arc', icon: 'crate', origin: '1990s shooter game data',
    recovers: 'Directory of named files',
    check: 'Directory and data tiling', kind: 'structure', samples: 1, silent: 37.86 },
];

const GROUP_LABEL = { rev: 'Reverse-engineered', doc: 'Document', arc: 'Tape / archive' };
const GROUP_TINT = { rev: 'tint-lav', doc: 'tint-butter', arc: 'tint-mint' };
const KIND_LABEL = { checksum: 'Checksummed', value: 'Value checks', structure: 'Structure only' };

function card(f) {
  const pct = Math.max(1.5, (f.silent / 40) * 100);          // bar scale: 0–40 %
  return `
  <article class="fmt" data-group="${f.group}">
    <div class="fmt-art ${GROUP_TINT[f.group]}">
      <canvas data-pixel="${f.icon}" class="px" aria-hidden="true"></canvas>
      <span class="fmt-kind chip-${f.kind}">${KIND_LABEL[f.kind]}</span>
    </div>
    <div class="fmt-body">
      <h3>${f.name}</h3>
      <p class="fmt-origin">${f.origin}</p>
      <p class="fmt-check">${f.check}</p>
      <div class="fmt-meter" title="Damaged copies that came out wrong with no warning, in our benchmark">
        <div class="fmt-meter-top"><span>Undetected damage</span><b>${f.silent.toFixed(f.silent ? 1 : 1)}%</b></div>
        <div class="fmt-bar"><span class="kind-${f.kind}" style="width:${pct}%"></span></div>
      </div>
    </div>
  </article>`;
}

const grid = document.getElementById('collectionGrid');
if (grid) {
  grid.innerHTML = FORMATS.map(card).join('');
  paint(grid);
  document.querySelectorAll('.filter-tabs .tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.filter-tabs .tab').forEach(t => {
        t.classList.toggle('active', t === tab);
        t.setAttribute('aria-selected', t === tab ? 'true' : 'false');
      });
      const g = tab.dataset.filter;
      grid.querySelectorAll('.fmt').forEach(c => { c.hidden = g !== 'all' && c.dataset.group !== g; });
    });
  });
}
