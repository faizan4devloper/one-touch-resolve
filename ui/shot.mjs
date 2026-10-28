import { createRequire } from "module";
const require = createRequire("/home/ec2-user/environment/agentic-studio-arch/");
const puppeteer = require("puppeteer");
const url=process.argv[2],out=process.argv[3],w=+(process.argv[4]||700),h=+(process.argv[5]||900);
const b=await puppeteer.launch({headless:"new",args:["--no-sandbox","--disable-setuid-sandbox"]});
const p=await b.newPage(); await p.setViewport({width:w,height:h,deviceScaleFactor:2});
await p.goto(url,{waitUntil:"networkidle2",timeout:30000}); await new Promise(r=>setTimeout(r,2500));
await p.screenshot({path:out}); await b.close(); console.log("wrote",out);
