"""Refresh only tracked frontend/functions before a long-running snapshot deploy."""
import subprocess

def run(*args):return subprocess.check_output(['git',*args],text=True).strip()
def main():
    subprocess.run(['git','fetch','--depth=1','origin','main'],check=True)
    names=run('ls-tree','-r','--name-only','origin/main','--','web','functions').splitlines()
    selected=[n for n in names if n.startswith('functions/') or (n.startswith('web/') and n.endswith(('.html','.css','.js','.mjs','.svg','.woff2'))) or n=='web/_routes.json']
    if not selected:raise RuntimeError('No site assets found')
    subprocess.run(['git','restore','--source=origin/main','--worktree','--',*selected],check=True)
    print('Site assets refreshed from',run('rev-parse','origin/main')[:12])
if __name__=='__main__':main()
