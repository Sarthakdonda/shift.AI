// Wrap static JSX copy in the localization component and keep both catalogs aligned.
// Run after adding UI copy: node tools/sync_ui_catalog.cjs
const ts=require('../frontend/node_modules/typescript');
const fs=require('fs');const path=require('path');
const root=path.resolve(__dirname,'..');const labels=new Set();
function walk(dir){return fs.readdirSync(dir,{withFileTypes:true}).flatMap(e=>e.isDirectory()?walk(path.join(dir,e.name)):[path.join(dir,e.name)]);}
for(const file of [...walk(path.join(root,'frontend/app')),...walk(path.join(root,'frontend/components'))].filter(p=>p.endsWith('.tsx')&&!p.endsWith('locale.tsx'))){
  let source=fs.readFileSync(file,'utf8').replace(/^\uFEFF/,'').trimStart();const tree=ts.createSourceFile(file,source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);const edits=[];
  function visit(node){
    if(ts.isJsxText(node)){
      const raw=node.getFullText(); const lines=raw.split(/\r?\n/);const text=lines.map((line,i)=>{let s=line.replace(/\t/g,' ');if(i>0)s=s.replace(/^ +/,'');if(i<lines.length-1)s=s.replace(/ +$/,'');return s;}).filter(Boolean).join(' ').replace(/&amp;/g,'&').replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&quot;/g,'\"').replace(/&#39;/g,"'");
      const parent=node.parent;const tag=parent&&ts.isJsxElement(parent)?parent.openingElement.tagName.getText(tree):'';
      if(/[A-Za-z]{2}/.test(text)&&!['T','code','pre','script','style','option'].includes(tag)){
        labels.add(text);edits.push({start:node.pos,end:node.end,text:`<T text={${JSON.stringify(text)}} />`});
      }
    }
    if(ts.isJsxAttribute(node)&&['title','label','placeholder','aria-label','text'].includes(node.name.getText(tree))&&node.initializer){
      if(ts.isStringLiteral(node.initializer)) labels.add(node.initializer.text);
      else if(ts.isJsxExpression(node.initializer)&&node.initializer.expression&&ts.isStringLiteral(node.initializer.expression)) labels.add(node.initializer.expression.text);
    }
    ts.forEachChild(node,visit);
  }
  visit(tree);
  if(edits.length){for(const edit of edits.sort((a,b)=>b.start-a.start))source=source.slice(0,edit.start)+edit.text+source.slice(edit.end);
    if(!/import\s*\{[^}]*\bT\b[^}]*\}\s*from\s*['"]@\/components\/locale['"]/.test(source)){
      const directive=source.match(/^['"]use client['"];?\s*/);
      const at=directive?directive[0].length:0;
      source=source.slice(0,at)+"\nimport {T} from '@/components/locale';\n"+source.slice(at);
    }
    fs.writeFileSync(file,source);
  }
}
for(const label of ['Projects','New project','Discovery','Documents','Analysis','Solution','Red Team','Blueprint','Deliverables','Teams & admin','Transformation','Email address','Password','Full name','Confirm password','Create account','Sign in','Sign up','Welcome back.','Create your workspace.','Create your account.','A fresh perspective starts here.','Sign in and pick up where you left off.','New to shift.AI?','Already have an account?','Signing in…','Creating your account…','Forgot password?','Reset your password.','Check your email.','Send reset link','Sending your link…','Choose a new password.','This link has expired.','Update password','Updating your password…','Checking your link…','New password','Confirm new password','Continue with Google','Please wait…','Business analysis','Architecture design','Process intelligence','Experience design','Database and API design','Delivery and estimation','Transformation strategy'])labels.add(label);
const serialized=JSON.stringify([...labels].sort(),null,2)+'\n';
fs.writeFileSync(path.join(root,'backend/app/core/ui_catalog.json'),serialized);
fs.writeFileSync(path.join(root,'frontend/lib/ui_catalog.json'),serialized);
console.log(`Synchronized ${labels.size} interface phrases.`);
