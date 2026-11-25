"""Build the Persian AUT thesis with isolated auxiliary files.

Requirements: XeLaTeX and the fonts named in commands.tex.
BibTeX/plain-fa is used only if a bibliography is enabled in the manuscript.
Use --no-publish while reviewing a draft in _build.
"""
from pathlib import Path
import argparse, hashlib, json, os, shutil, subprocess, sys

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / '_build'

def run(args, cwd, env, log):
    with log.open('w', encoding='utf8') as out:
        result = subprocess.run(args, cwd=cwd, env=env, stdout=out,
                                stderr=subprocess.STDOUT, text=True,
                                encoding='utf8', errors='replace')
    if result.returncode:
        print(log.read_text(encoding='utf8')[-8000:])
        raise SystemExit(f'Build failed; see {log.name}')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-publish', action='store_true')
    args = parser.parse_args()
    BUILD.mkdir(exist_ok=True)
    env = os.environ.copy()
    # The build directory MUST precede the template's old generated files.
    env['TEXINPUTS'] = os.pathsep.join([str(BUILD), str(ROOT), ''])
    env['BIBINPUTS'] = os.pathsep.join([str(BUILD), str(ROOT), ''])
    xelatex = shutil.which('xelatex')
    bibtex = shutil.which('bibtex')
    if not xelatex:
        raise SystemExit('XeLaTeX must be available in PATH.')
    texargs = [xelatex, '-interaction=nonstopmode', '-halt-on-error',
               '-file-line-error', '-output-directory='+str(BUILD), 'AUTthesis.tex']
    run(texargs, ROOT, env, BUILD/'xelatex-1.txt')
    aux=(BUILD/'AUTthesis.aux').read_text(encoding='utf8',errors='replace')
    if r'\bibdata{' in aux:
        if not bibtex:raise SystemExit('BibTeX is required by the enabled bibliography.')
        run([bibtex, 'AUTthesis'], BUILD, env, BUILD/'bibtex.txt')
    for number in [2, 3, 4]:
        run(texargs, ROOT, env, BUILD/f'xelatex-{number}.txt')
    log = (BUILD/'AUTthesis.log').read_text(encoding='utf8', errors='replace')
    fatal = ['Missing character:', 'There were undefined references',
             'multiply defined', 'Overfull \\hbox', 'Overfull \\vbox',
             'Rerun to get cross-references right', 'LaTeX Error:']
    problems = [item for item in fatal if item in log]
    if problems:
        raise SystemExit('Review the final TeX log: '+', '.join(problems))
    pdf = BUILD/'AUTthesis.pdf'
    if not args.no_publish:
        shutil.copy2(pdf, ROOT/pdf.name)
    sources = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted(ROOT.glob('*.tex'))}
    sources.update({p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in [ROOT/'AUTthesis.cls', ROOT/'references.bib']})
    sources['build_thesis.py']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    record = {'pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),
              'sources':sources, 'published':not args.no_publish,
              'scope':'algorithm-only, base cost; other headings intentionally empty'}
    (BUILD/'build-manifest.json').write_text(json.dumps(record, indent=2,
                                                ensure_ascii=False), encoding='utf8')
    print('Built successfully:', pdf.name)

if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):sys.stdout.reconfigure(encoding='utf8')
    main()
