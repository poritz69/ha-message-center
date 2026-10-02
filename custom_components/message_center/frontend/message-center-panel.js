var Qe=Object.defineProperty;var Xe=Object.getOwnPropertyDescriptor;var u=(r,s,e,t)=>{for(var i=t>1?void 0:t?Xe(s,e):s,n=r.length-1,a;n>=0;n--)(a=r[n])&&(i=(t?a(s,e,i):a(i))||i);return t&&i&&Qe(s,e,i),i};var V=globalThis,J=V.ShadowRoot&&(V.ShadyCSS===void 0||V.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,se=Symbol(),ve=new WeakMap,U=class{constructor(s,e,t){if(this._$cssResult$=!0,t!==se)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=s,this.t=e}get styleSheet(){let s=this.o,e=this.t;if(J&&s===void 0){let t=e!==void 0&&e.length===1;t&&(s=ve.get(e)),s===void 0&&((this.o=s=new CSSStyleSheet).replaceSync(this.cssText),t&&ve.set(e,s))}return s}toString(){return this.cssText}},be=r=>new U(typeof r=="string"?r:r+"",void 0,se),N=(r,...s)=>{let e=r.length===1?r[0]:s.reduce((t,i,n)=>t+(a=>{if(a._$cssResult$===!0)return a.cssText;if(typeof a=="number")return a;throw Error("Value passed to 'css' function must be a 'css' function result: "+a+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(i)+r[n+1],r[0]);return new U(e,r,se)},ye=(r,s)=>{if(J)r.adoptedStyleSheets=s.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(let e of s){let t=document.createElement("style"),i=V.litNonce;i!==void 0&&t.setAttribute("nonce",i),t.textContent=e.cssText,r.appendChild(t)}},ne=J?r=>r:r=>r instanceof CSSStyleSheet?(s=>{let e="";for(let t of s.cssRules)e+=t.cssText;return be(e)})(r):r;var{is:Ye,defineProperty:et,getOwnPropertyDescriptor:tt,getOwnPropertyNames:it,getOwnPropertySymbols:st,getPrototypeOf:nt}=Object,Q=globalThis,we=Q.trustedTypes,at=we?we.emptyScript:"",rt=Q.reactiveElementPolyfillSupport,I=(r,s)=>r,W={toAttribute(r,s){switch(s){case Boolean:r=r?at:null;break;case Object:case Array:r=r==null?r:JSON.stringify(r)}return r},fromAttribute(r,s){let e=r;switch(s){case Boolean:e=r!==null;break;case Number:e=r===null?null:Number(r);break;case Object:case Array:try{e=JSON.parse(r)}catch{e=null}}return e}},X=(r,s)=>!Ye(r,s),xe={attribute:!0,type:String,converter:W,reflect:!1,useDefault:!1,hasChanged:X};Symbol.metadata??=Symbol("metadata"),Q.litPropertyMetadata??=new WeakMap;var S=class extends HTMLElement{static addInitializer(s){this._$Ei(),(this.l??=[]).push(s)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(s,e=xe){if(e.state&&(e.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(s)&&((e=Object.create(e)).wrapped=!0),this.elementProperties.set(s,e),!e.noAccessor){let t=Symbol(),i=this.getPropertyDescriptor(s,t,e);i!==void 0&&et(this.prototype,s,i)}}static getPropertyDescriptor(s,e,t){let{get:i,set:n}=tt(this.prototype,s)??{get(){return this[e]},set(a){this[e]=a}};return{get:i,set(a){let p=i?.call(this);n?.call(this,a),this.requestUpdate(s,p,t)},configurable:!0,enumerable:!0}}static getPropertyOptions(s){return this.elementProperties.get(s)??xe}static _$Ei(){if(this.hasOwnProperty(I("elementProperties")))return;let s=nt(this);s.finalize(),s.l!==void 0&&(this.l=[...s.l]),this.elementProperties=new Map(s.elementProperties)}static finalize(){if(this.hasOwnProperty(I("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(I("properties"))){let e=this.properties,t=[...it(e),...st(e)];for(let i of t)this.createProperty(i,e[i])}let s=this[Symbol.metadata];if(s!==null){let e=litPropertyMetadata.get(s);if(e!==void 0)for(let[t,i]of e)this.elementProperties.set(t,i)}this._$Eh=new Map;for(let[e,t]of this.elementProperties){let i=this._$Eu(e,t);i!==void 0&&this._$Eh.set(i,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(s){let e=[];if(Array.isArray(s)){let t=new Set(s.flat(1/0).reverse());for(let i of t)e.unshift(ne(i))}else s!==void 0&&e.push(ne(s));return e}static _$Eu(s,e){let t=e.attribute;return t===!1?void 0:typeof t=="string"?t:typeof s=="string"?s.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(s=>this.enableUpdating=s),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(s=>s(this))}addController(s){(this._$EO??=new Set).add(s),this.renderRoot!==void 0&&this.isConnected&&s.hostConnected?.()}removeController(s){this._$EO?.delete(s)}_$E_(){let s=new Map,e=this.constructor.elementProperties;for(let t of e.keys())this.hasOwnProperty(t)&&(s.set(t,this[t]),delete this[t]);s.size>0&&(this._$Ep=s)}createRenderRoot(){let s=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return ye(s,this.constructor.elementStyles),s}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(s=>s.hostConnected?.())}enableUpdating(s){}disconnectedCallback(){this._$EO?.forEach(s=>s.hostDisconnected?.())}attributeChangedCallback(s,e,t){this._$AK(s,t)}_$ET(s,e){let t=this.constructor.elementProperties.get(s),i=this.constructor._$Eu(s,t);if(i!==void 0&&t.reflect===!0){let n=(t.converter?.toAttribute!==void 0?t.converter:W).toAttribute(e,t.type);this._$Em=s,n==null?this.removeAttribute(i):this.setAttribute(i,n),this._$Em=null}}_$AK(s,e){let t=this.constructor,i=t._$Eh.get(s);if(i!==void 0&&this._$Em!==i){let n=t.getPropertyOptions(i),a=typeof n.converter=="function"?{fromAttribute:n.converter}:n.converter?.fromAttribute!==void 0?n.converter:W;this._$Em=i;let p=a.fromAttribute(e,n.type);this[i]=p??this._$Ej?.get(i)??p,this._$Em=null}}requestUpdate(s,e,t,i=!1,n){if(s!==void 0){let a=this.constructor;if(i===!1&&(n=this[s]),t??=a.getPropertyOptions(s),!((t.hasChanged??X)(n,e)||t.useDefault&&t.reflect&&n===this._$Ej?.get(s)&&!this.hasAttribute(a._$Eu(s,t))))return;this.C(s,e,t)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(s,e,{useDefault:t,reflect:i,wrapped:n},a){t&&!(this._$Ej??=new Map).has(s)&&(this._$Ej.set(s,a??e??this[s]),n!==!0||a!==void 0)||(this._$AL.has(s)||(this.hasUpdated||t||(e=void 0),this._$AL.set(s,e)),i===!0&&this._$Em!==s&&(this._$Eq??=new Set).add(s))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}let s=this.scheduleUpdate();return s!=null&&await s,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[i,n]of this._$Ep)this[i]=n;this._$Ep=void 0}let t=this.constructor.elementProperties;if(t.size>0)for(let[i,n]of t){let{wrapped:a}=n,p=this[i];a!==!0||this._$AL.has(i)||p===void 0||this.C(i,void 0,n,p)}}let s=!1,e=this._$AL;try{s=this.shouldUpdate(e),s?(this.willUpdate(e),this._$EO?.forEach(t=>t.hostUpdate?.()),this.update(e)):this._$EM()}catch(t){throw s=!1,this._$EM(),t}s&&this._$AE(e)}willUpdate(s){}_$AE(s){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(s)),this.updated(s)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(s){return!0}update(s){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(s){}firstUpdated(s){}};S.elementStyles=[],S.shadowRootOptions={mode:"open"},S[I("elementProperties")]=new Map,S[I("finalized")]=new Map,rt?.({ReactiveElement:S}),(Q.reactiveElementVersions??=[]).push("2.1.2");var pe=globalThis,$e=r=>r,Y=pe.trustedTypes,ke=Y?Y.createPolicy("lit-html",{createHTML:r=>r}):void 0,He="$lit$",M=`lit$${Math.random().toFixed(9).slice(2)}$`,Me="?"+M,ot=`<${Me}>`,D=document,Z=()=>D.createComment(""),B=r=>r===null||typeof r!="object"&&typeof r!="function",he=Array.isArray,lt=r=>he(r)||typeof r?.[Symbol.iterator]=="function",ae=`[ 	
\f\r]`,F=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,Ae=/-->/g,Se=/>/g,R=RegExp(`>|${ae}(?:([^\\s"'>=/]+)(${ae}*=${ae}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),Ee=/'/g,ze=/"/g,Ne=/^(?:script|style|textarea|title)$/i,ue=r=>(s,...e)=>({_$litType$:r,strings:s,values:e}),l=ue(1),f=ue(2),Ht=ue(3),O=Symbol.for("lit-noChange"),d=Symbol.for("lit-nothing"),Te=new WeakMap,L=D.createTreeWalker(D,129);function Re(r,s){if(!he(r)||!r.hasOwnProperty("raw"))throw Error("invalid template strings array");return ke!==void 0?ke.createHTML(s):s}var ct=(r,s)=>{let e=r.length-1,t=[],i,n=s===2?"<svg>":s===3?"<math>":"",a=F;for(let p=0;p<e;p++){let o=r[p],m,c,h=-1,$=0;for(;$<o.length&&(a.lastIndex=$,c=a.exec(o),c!==null);)$=a.lastIndex,a===F?c[1]==="!--"?a=Ae:c[1]!==void 0?a=Se:c[2]!==void 0?(Ne.test(c[2])&&(i=RegExp("</"+c[2],"g")),a=R):c[3]!==void 0&&(a=R):a===R?c[0]===">"?(a=i??F,h=-1):c[1]===void 0?h=-2:(h=a.lastIndex-c[2].length,m=c[1],a=c[3]===void 0?R:c[3]==='"'?ze:Ee):a===ze||a===Ee?a=R:a===Ae||a===Se?a=F:(a=R,i=void 0);let g=a===R&&r[p+1].startsWith("/>")?" ":"";n+=a===F?o+ot:h>=0?(t.push(m),o.slice(0,h)+He+o.slice(h)+M+g):o+M+(h===-2?p:g)}return[Re(r,n+(r[e]||"<?>")+(s===2?"</svg>":s===3?"</math>":"")),t]},G=class r{constructor({strings:s,_$litType$:e},t){let i;this.parts=[];let n=0,a=0,p=s.length-1,o=this.parts,[m,c]=ct(s,e);if(this.el=r.createElement(m,t),L.currentNode=this.el.content,e===2||e===3){let h=this.el.content.firstChild;h.replaceWith(...h.childNodes)}for(;(i=L.nextNode())!==null&&o.length<p;){if(i.nodeType===1){if(i.hasAttributes())for(let h of i.getAttributeNames())if(h.endsWith(He)){let $=c[a++],g=i.getAttribute(h).split(M),z=/([.?@])?(.*)/.exec($);o.push({type:1,index:n,name:z[2],strings:g,ctor:z[1]==="."?oe:z[1]==="?"?le:z[1]==="@"?ce:P}),i.removeAttribute(h)}else h.startsWith(M)&&(o.push({type:6,index:n}),i.removeAttribute(h));if(Ne.test(i.tagName)){let h=i.textContent.split(M),$=h.length-1;if($>0){i.textContent=Y?Y.emptyScript:"";for(let g=0;g<$;g++)i.append(h[g],Z()),L.nextNode(),o.push({type:2,index:++n});i.append(h[$],Z())}}}else if(i.nodeType===8)if(i.data===Me)o.push({type:2,index:n});else{let h=-1;for(;(h=i.data.indexOf(M,h+1))!==-1;)o.push({type:7,index:n}),h+=M.length-1}n++}}static createElement(s,e){let t=D.createElement("template");return t.innerHTML=s,t}};function C(r,s,e=r,t){if(s===O)return s;let i=t!==void 0?e._$Co?.[t]:e._$Cl,n=B(s)?void 0:s._$litDirective$;return i?.constructor!==n&&(i?._$AO?.(!1),n===void 0?i=void 0:(i=new n(r),i._$AT(r,e,t)),t!==void 0?(e._$Co??=[])[t]=i:e._$Cl=i),i!==void 0&&(s=C(r,i._$AS(r,s.values),i,t)),s}var re=class{constructor(s,e){this._$AV=[],this._$AN=void 0,this._$AD=s,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(s){let{el:{content:e},parts:t}=this._$AD,i=(s?.creationScope??D).importNode(e,!0);L.currentNode=i;let n=L.nextNode(),a=0,p=0,o=t[0];for(;o!==void 0;){if(a===o.index){let m;o.type===2?m=new j(n,n.nextSibling,this,s):o.type===1?m=new o.ctor(n,o.name,o.strings,this,s):o.type===6&&(m=new de(n,this,s)),this._$AV.push(m),o=t[++p]}a!==o?.index&&(n=L.nextNode(),a++)}return L.currentNode=D,i}p(s){let e=0;for(let t of this._$AV)t!==void 0&&(t.strings!==void 0?(t._$AI(s,t,e),e+=t.strings.length-2):t._$AI(s[e])),e++}},j=class r{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(s,e,t,i){this.type=2,this._$AH=d,this._$AN=void 0,this._$AA=s,this._$AB=e,this._$AM=t,this.options=i,this._$Cv=i?.isConnected??!0}get parentNode(){let s=this._$AA.parentNode,e=this._$AM;return e!==void 0&&s?.nodeType===11&&(s=e.parentNode),s}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(s,e=this){s=C(this,s,e),B(s)?s===d||s==null||s===""?(this._$AH!==d&&this._$AR(),this._$AH=d):s!==this._$AH&&s!==O&&this._(s):s._$litType$!==void 0?this.$(s):s.nodeType!==void 0?this.T(s):lt(s)?this.k(s):this._(s)}O(s){return this._$AA.parentNode.insertBefore(s,this._$AB)}T(s){this._$AH!==s&&(this._$AR(),this._$AH=this.O(s))}_(s){this._$AH!==d&&B(this._$AH)?this._$AA.nextSibling.data=s:this.T(D.createTextNode(s)),this._$AH=s}$(s){let{values:e,_$litType$:t}=s,i=typeof t=="number"?this._$AC(s):(t.el===void 0&&(t.el=G.createElement(Re(t.h,t.h[0]),this.options)),t);if(this._$AH?._$AD===i)this._$AH.p(e);else{let n=new re(i,this),a=n.u(this.options);n.p(e),this.T(a),this._$AH=n}}_$AC(s){let e=Te.get(s.strings);return e===void 0&&Te.set(s.strings,e=new G(s)),e}k(s){he(this._$AH)||(this._$AH=[],this._$AR());let e=this._$AH,t,i=0;for(let n of s)i===e.length?e.push(t=new r(this.O(Z()),this.O(Z()),this,this.options)):t=e[i],t._$AI(n),i++;i<e.length&&(this._$AR(t&&t._$AB.nextSibling,i),e.length=i)}_$AR(s=this._$AA.nextSibling,e){for(this._$AP?.(!1,!0,e);s!==this._$AB;){let t=$e(s).nextSibling;$e(s).remove(),s=t}}setConnected(s){this._$AM===void 0&&(this._$Cv=s,this._$AP?.(s))}},P=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(s,e,t,i,n){this.type=1,this._$AH=d,this._$AN=void 0,this.element=s,this.name=e,this._$AM=i,this.options=n,t.length>2||t[0]!==""||t[1]!==""?(this._$AH=Array(t.length-1).fill(new String),this.strings=t):this._$AH=d}_$AI(s,e=this,t,i){let n=this.strings,a=!1;if(n===void 0)s=C(this,s,e,0),a=!B(s)||s!==this._$AH&&s!==O,a&&(this._$AH=s);else{let p=s,o,m;for(s=n[0],o=0;o<n.length-1;o++)m=C(this,p[t+o],e,o),m===O&&(m=this._$AH[o]),a||=!B(m)||m!==this._$AH[o],m===d?s=d:s!==d&&(s+=(m??"")+n[o+1]),this._$AH[o]=m}a&&!i&&this.j(s)}j(s){s===d?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,s??"")}},oe=class extends P{constructor(){super(...arguments),this.type=3}j(s){this.element[this.name]=s===d?void 0:s}},le=class extends P{constructor(){super(...arguments),this.type=4}j(s){this.element.toggleAttribute(this.name,!!s&&s!==d)}},ce=class extends P{constructor(s,e,t,i,n){super(s,e,t,i,n),this.type=5}_$AI(s,e=this){if((s=C(this,s,e,0)??d)===O)return;let t=this._$AH,i=s===d&&t!==d||s.capture!==t.capture||s.once!==t.once||s.passive!==t.passive,n=s!==d&&(t===d||i);i&&this.element.removeEventListener(this.name,this,t),n&&this.element.addEventListener(this.name,this,s),this._$AH=s}handleEvent(s){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,s):this._$AH.handleEvent(s)}},de=class{constructor(s,e,t){this.element=s,this.type=6,this._$AN=void 0,this._$AM=e,this.options=t}get _$AU(){return this._$AM._$AU}_$AI(s){C(this,s)}};var dt=pe.litHtmlPolyfillSupport;dt?.(G,j),(pe.litHtmlVersions??=[]).push("3.3.3");var Le=(r,s,e)=>{let t=e?.renderBefore??s,i=t._$litPart$;if(i===void 0){let n=e?.renderBefore??null;t._$litPart$=i=new j(s.insertBefore(Z(),n),n,void 0,e??{})}return i._$AI(r),i};var me=globalThis,k=class extends S{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let s=super.createRenderRoot();return this.renderOptions.renderBefore??=s.firstChild,s}update(s){let e=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(s),this._$Do=Le(e,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return O}};k._$litElement$=!0,k.finalized=!0,me.litElementHydrateSupport?.({LitElement:k});var pt=me.litElementPolyfillSupport;pt?.({LitElement:k});(me.litElementVersions??=[]).push("4.2.2");var ht={attribute:!0,type:String,converter:W,reflect:!1,hasChanged:X},ut=(r=ht,s,e)=>{let{kind:t,metadata:i}=e,n=globalThis.litPropertyMetadata.get(i);if(n===void 0&&globalThis.litPropertyMetadata.set(i,n=new Map),t==="setter"&&((r=Object.create(r)).wrapped=!0),n.set(e.name,r),t==="accessor"){let{name:a}=e;return{set(p){let o=s.get.call(this);s.set.call(this,p),this.requestUpdate(a,o,r,!0,p)},init(p){return p!==void 0&&this.C(a,void 0,r,p),p}}}if(t==="setter"){let{name:a}=e;return function(p){let o=this[a];s.call(this,p),this.requestUpdate(a,o,r,!0,p)}}throw Error("Unsupported decorator location: "+t)};function y(r){return(s,e)=>typeof e=="object"?ut(r,s,e):((t,i,n)=>{let a=i.hasOwnProperty(n);return i.constructor.createProperty(n,t),a?Object.getOwnPropertyDescriptor(i,n):void 0})(r,s,e)}function v(r){return y({...r,state:!0,attribute:!1})}var x="message_center",De=r=>r.callWS({type:`${x}/overview`}),Oe=r=>r.callWS({type:`${x}/messages`}),_e=r=>r.callWS({type:`${x}/history`}),Ce=r=>r.callWS({type:`${x}/config`}),K=(r,s,e,t)=>r.callWS({type:`${x}/save`,kind:s,data:e,...t?{subentry_id:t}:{}}),Pe=(r,s)=>r.callWS({type:`${x}/delete`,subentry_id:s}),te=(r,s,e,t={})=>r.callWS({type:`${x}/action`,action:s,message_id:e,...t}),Ke=(r,s,e)=>r.callWS({type:`${x}/dismiss_unknown`,origin:s,title:e}),ge=(r,s)=>r.callWS({type:`${x}/options`,options:s}),Ue=(r,s)=>r.callWS({type:`${x}/recipients`,actions:s}),Ie=(r,s)=>r.callWS({type:`${x}/test`,priority:s}),We=r=>r.callWS({type:`${x}/alarm_off`}),Fe=r=>r.callWS({type:`${x}/scan`}),Ze=(r,s)=>r.connection.subscribeMessage(()=>s(),{type:`${x}/subscribe`});async function Be(){if(customElements.get("ha-form")&&customElements.get("ha-dialog"))return;let r=window.loadCardHelpers;if(r)try{await(await(await r()).createCardElement({type:"entities",entities:[]})).constructor.getConfigElement?.()}catch{}}var mt={title:"Message Center",q_open:"\u201E",q_close:"\u201C",overview:"\xDCbersicht",open:"Offen",history:"Verlauf",kinds:"Meldungen",groups:"Gruppen",rules:"Zustellregeln",recipients:"Empf\xE4nger",ready:"Bereit",not_ready:"Nicht bereit",waiting:"Wartend",disturbed:"Gest\xF6rt",new:"Neu",active_rules:"Aktive Regeln",delivered_today:"Zugestellt heute",last_delivery:"Letzte Zustellung",none_yet:"noch keine",new_title:"Neu, bitte bewerten",new_empty:"Keine unbewerteten Nachrichten.",classify:"Bewerten",count:"Anzahl",last_seen:"zuletzt",origin:"Herkunft",unknown_origin:"unbekannte Herkunft",from_any:"jede Herkunft",open_empty:"Nichts offen. Alles zugestellt.",send_now:"Jetzt senden",discard:"Verwerfen",snooze:"Sp\xE4ter",forward:"An KI",state:"Zustand",reason:"Grund",since:"seit",until:"bis",next_try:"n\xE4chster Versuch",recipients_failed:"gescheitert",history_empty:"Noch nichts im Verlauf.",recent:"Zuletzt beendet",older:"\xC4lter",all_groups:"Alle Gruppen",no_group:"ohne Gruppe",search:"Suchen",add_kind:"Meldungsart anlegen",edit:"Bearbeiten",delete:"L\xF6schen",add_group:"Gruppe anlegen",add_rule:"Zustellregel anlegen",save:"Speichern",cancel:"Abbrechen",confirm_delete:"Wirklich l\xF6schen?",name:"Name",title_mode:"Titelbedingung",exact:"genau",prefix:"beginnt mit",contains:"enth\xE4lt",title_value:"Text der Bedingung",group:"Gruppe",group_id:"Gruppe",priority:"Stufe",new_group:"Neue Gruppe anlegen",new_group_helper:"Nur ausf\xFCllen, wenn es die Gruppe noch nicht gibt. Sie \xFCbernimmt Stufe, Abstand und Verfall dieser Meldungsart als Vorgaben.",required_missing:"Bitte Name und Text der Bedingung ausf\xFCllen.",unassigned:"Ohne Zuweisung",defaults:"Vorgaben",group_empty:"Noch keine Meldungsarten in dieser Gruppe.",unassigned_empty:"Alle Meldungsarten sind einer Gruppe zugewiesen.",p1:"1 \xB7 Hinweis",p2:"2 \xB7 Wichtig",p3:"3 \xB7 Alarm",no_hold:"Nicht zur\xFCckhalten",spacing:"Abstand (Minuten, 0 = keiner)",expires_after:"Verfall (Minuten, 0 = nie)",light:"Lichtimpuls",light_auto:"nach Stufe",light_on:"immer",light_off:"nie",active:"Aktiv",icon:"Symbol (mdi:\u2026)",entity:"Entit\xE4t",rule_state:"Zustand der Entit\xE4t",effect_1:"Wirkung Stufe 1",effect_2:"Wirkung Stufe 2",effect_3:"Wirkung Stufe 3",pass:"durchlassen",hold:"zur\xFCckhalten",discard_effect:"verwerfen",max_hours:"H\xF6chstdauer (Stunden)",current:"aktuell",expired:"abgelaufen",unknown_state:"Entit\xE4t unbekannt",rule_inactive:"nicht aktiv",kinds_empty:"Noch keine Meldungsarten. Unbewertete Nachrichten stehen in der \xDCbersicht.",groups_empty:"Noch keine Gruppen.",rules_empty:"Noch keine Zustellregeln. Eine Regel h\xE4lt Meldungen zur\xFCck, solange eine Entit\xE4t einen bestimmten Zustand hat, zum Beispiel ein Helfer \u201ENachtmodus\u201C = an, und liefert sie danach. Stufe 3 (Alarm) geht in der Regel trotzdem durch. Den Helfer zuerst in HA anlegen (Einstellungen \u2192 Ger\xE4te & Dienste \u2192 Helfer \u2192 Schalter), dann hier die Regel.",configured:"eingerichtet",available:"erreichbar",unavailable:"nicht erreichbar",recipients_hint:"Beim Einrichten der Integration wird ein erstes Handy gew\xE4hlt; danach werden Empf\xE4nger hier verwaltet. Neue Handys erscheinen, sobald ihre Companion-App eingerichtet ist.",minutes:"Minuten",note:"Notiz f\xFCr die KI",messages:"Nachrichten",delivered:"zugestellt",failed:"gescheitert",discarded:"verworfen",unclear:"unklar",sending:"wird gesendet",retrying:"wiederholen",generation:"Generation",error:"Fehler",loading:"Lade \u2026",not_set_up:"Message Center ist nicht eingerichtet.",text:"Text",labels:"Labels",kind:"Meldungsart",ev_snoozed:"zur\xFCckgestellt",ev_forwarded:"an KI weitergeleitet",ev_discarded:"verworfen",ev_sent_now:"jetzt gesendet",ev_light:"Lichtimpuls",ev_light_skipped:"Lichtimpuls \xFCbersprungen",ev_light_failed:"Lichtimpuls verweigert (kein Recht an den Lampen)",spacing_skip:"Mindestabstand zwischen Lichtimpulsen",nothing_on:"keine Lampe an",effect_skip:"Meldung aus eigener Wirkung",pulse_ms:"Dauer des Impulses (Millisekunden aus)",light_spacing:"Mindestabstand zwischen Lichtimpulsen (Sekunden, 0 = keiner)",light_spacing_helper:"Gegen Dauerflackern, wenn mehrere Stufe-2-Meldungen kurz nacheinander kommen. Innerhalb des Abstands wird der Impuls \xFCbersprungen und unter der Nachricht vermerkt. Tests ignorieren ihn.",test:"Test",test_hint:"\u201ETest\u201C schickt eine Testmeldung dieser Stufe an alle Empf\xE4nger: ohne Verlauf, ohne Kn\xF6pfe, mit den gespeicherten Einstellungen.",test_sent:"Test Stufe {n} gesendet an {names}",test_lights:"Lichtimpuls an {lights}",test_no_lights:"kein Lichtimpuls (keine gew\xE4hlte Lampe an)",test_failed:"nicht erreicht: {names}",confirm_alarm_test:"Wirklich einen Alarm-Test senden? Er umgeht \u201ENicht st\xF6ren\u201C und ist laut.",src_phone:"vom Handy",src_page:"auf der Seite",src_action:"per Aktion",src_center:"durch die Zentrale",settings:"Einstellungen",dismiss:"Verwerfen",guide_title:"Willkommen im Message Center",guide_dismiss:"Verstanden, ausblenden",guide_show:"Einf\xFChrung wieder anzeigen",guide_1:"Absender: Automationen und Skripte rufen die Aktion notify.message_center mit Titel und Text auf, statt direkt das Handy. Alles Weitere regelt die Zentrale.",guide_2:"Neu, bitte bewerten: Jede neue Sorte Meldung taucht in der \xDCbersicht auf. \u201EBewerten\u201C macht daraus eine Meldungsart mit Stufe, Gruppe, Abstand und Verfall. Unbewertete Meldungen gehen als Stufe 1 raus.",guide_3:"Stufen: 1 Hinweis = Push. 2 Wichtig = Push und Lichtimpuls an gew\xE4hlten Lampen. 3 Alarm = Push, der \u201ENicht st\xF6ren\u201C umgeht. Unter Einstellungen \u2192 Stufe \u2192 Wirkung, dort auch die Test-Kn\xF6pfe.",guide_4:"Zustellregeln: Solange eine Entit\xE4t einen Zustand hat, zum Beispiel ein Helfer \u201ENachtmodus\u201C = an, werden Stufe 1 und 2 zur\xFCckgehalten und danach zugestellt. Alarm geht durch. Helfer zuerst in HA anlegen, dann die Regel im Reiter Zustellregeln.",guide_5:"Handy: \u201ESp\xE4ter\u201C stellt eine Meldung zur\xFCck, \u201EAn KI\u201C reicht sie weiter. Empf\xE4nger und Kn\xF6pfe stellst du unter Empf\xE4nger und Einstellungen ein. Der Verlauf zeigt alles, was durch ist, samt Eingriffen.",kinds_one:"1 Meldung",kinds_many:"{n} Meldungen",levels_title:"Stufe \u2192 Wirkung",level_1_name:"Hinweis",level_1_effect:"Push aufs Handy. Bei aktiver Zustellregel zur\xFCckgehalten, au\xDFer die Meldungsart hat \u201ENicht zur\xFCckhalten\u201C.",level_2_name:"Wichtig",level_2_effect:"Push aufs Handy, dazu ein Lichtimpuls: die gew\xE4hlten Lampen und Schalter gehen kurz aus und wieder an, nur die, die gerade an sind (au\xDFer sie stehen unten unter \u201Eauch wenn aus\u201C: dann kurz an und wieder aus). Dauer und Mindestabstand stehen unten. Der Schalter \u201ELichtimpuls\u201C am Ger\xE4t schaltet ihn ab. Je Meldungsart \xFCbersteuerbar (immer/nie).",level_3_name:"Alarm",level_3_effect:"Push auf dem Alarmkanal: Android mit voller Alarmlautst\xE4rke und dem Weckton des Ger\xE4ts (in den Android-Einstellungen unter T\xF6ne \xE4nderbar), umgeht \u201ENicht st\xF6ren\u201C; iPhone kritisch mit Ton (kritische Hinweise in der App erlauben). Dazu das Alarmlicht: Die gew\xE4hlten Lampen und Schalter gehen alle an und wechseln dann im Takt alle aus, alle an, bis der Alarm beendet wird, sp\xE4testens nach der H\xF6chstdauer. Danach kehren sie in ihren vorherigen Zustand zur\xFCck. Beenden: Knopf \u201EAlarm beenden\u201C auf dem Push, Schalter \u201EAlarm\u201C am Ger\xE4t, oder oben auf dieser Seite.",alarm_lights:"Lampen und Schalter f\xFCr das Alarmlicht",alarm_lights_helper:"Hue: einzelne Lampen w\xE4hlen, keine R\xE4ume oder Zonen. Die Hue-Bridge nimmt f\xFCr Gruppen nur einen Befehl pro Sekunde an, alles Weitere verwirft sie.",alarm_interval_ms:"Takt des Alarmlichts (Millisekunden; Zigbee-Lampen brauchen etwa 1000)",alarm_channel:"Alarmkanal auf Android",alarm_channel_helper:"\u201EAlarmstrom\u201C spielt den Standard-Weckton des Systems auf Alarmlautst\xE4rke; \u201Emax\u201C dasselbe auf voller Lautst\xE4rke, klappt nicht auf jedem Ger\xE4t. \u201EEigener Kanal\u201C: Ton, Vibration und \u201ENicht st\xF6ren\u201C-Ausnahme stellst du einmal in Android unter Benachrichtigungen \u2192 Home Assistant \u2192 Kanal \u201Emessage_center_alarm\u201C ein.",alarm_channel_stream:"Alarmstrom (Standard-Weckton)",alarm_channel_max:"Alarmstrom, volle Lautst\xE4rke",alarm_channel_own:"Eigener Kanal (in Android einstellbar)",alarm_tts:"Ansage: Titel per Sprachausgabe auf voller Alarmlautst\xE4rke vorlesen (Android)",alarm_max_seconds:"H\xF6chstdauer eines Alarms (Sekunden)",alarm_test_seconds:"Dauer beim Test (Sekunden)",alarm_active:"Alarm aktiv",alarm_end:"Alarm beenden",alarm_until:"bis",ev_alarm_light:"Alarmlicht",test_alarm:"Alarmlicht an {lights}",lights:"Lampen und Schalter f\xFCr den Lichtimpuls",lights_helper:"Leer = kein Lichtimpuls. Was gerade an ist, geht f\xFCr die Dauer unten aus und wieder an.",options_title:"Optionen",history_days:"Verlauf aufbewahren (Tage)",sidebar:"Eintrag in der Seitenleiste",hide_titles:"Titel nicht in Verlauf und Attribute schreiben",allow_alarm:"Stufe 3 (Alarm) auch \xFCber die Aktion send erlauben",silent_repeat:"Wiederholungen leise ersetzen (ohne Ton, nur Z\xE4hler im Titel)",saved:"Gespeichert.",used:"verwendet",buttons_title:"Kn\xF6pfe auf dem Push",buttons_intro:"Die Kn\xF6pfe erreichen HA nur, wenn das Handy HA erreicht: im Heimnetz, per VPN oder Nabu Casa.",button_snooze:"Knopf \u201ESp\xE4ter\u201C (Meldung zur\xFCckstellen)",button_forward:"Knopf \u201EAn KI\u201C (Meldung weiterleiten, Notiz eintippbar)",snooze_minutes:"Dauer f\xFCr \u201ESp\xE4ter\u201C (Minuten)",snooze_minutes_2:"Zweiter Knopf \u201ESp\xE4ter\u201C mit dieser Dauer (Minuten, 0 = kein zweiter Knopf)",snooze_input:"Minuten eintippen statt fester Kn\xF6pfe",snooze_input_helper:"Aus: ein Tipp gen\xFCgt, die Dauer steht auf dem Knopf. An: nach dem Tipp fragt das Handy nach der Minutenzahl; leer = erste Dauer.",recipients_intro:"Gefundene Handys mit Companion-App. Angehakte bekommen die Nachrichten. Mindestens eines muss verwendet werden.",at_least_one:"Mindestens ein Empf\xE4nger muss verwendet werden.",intro_open:"Alles, was noch nicht durch ist: wartend (Regel, Abstand, zur\xFCckgestellt), wird gesendet, Wiederholung nach Fehler oder unklar nach Neustart. \u201EJetzt senden\u201C umgeht die Regel, \u201EVerwerfen\u201C beendet die Nachricht ohne Zustellung.",intro_history:"Was zugestellt, verworfen oder gescheitert ist, samt Eingriffen. \u201EZuletzt beendet\u201C bleibt 24 Stunden im Arbeitsspeicher, \u201E\xC4lter\u201C so lange wie in den Einstellungen gew\xE4hlt.",intro_kinds:"Jede Meldungsart legt fest, wie eine Sorte Meldung behandelt wird: Stufe, Gruppe, Abstand, Verfall, Lichtimpuls. Die speziellste passende Art gewinnt. Meldungsarten lassen sich mit der Maus in eine andere Gruppe ziehen.",intro_rules:"Eine Regel h\xE4lt Meldungen zur\xFCck, solange eine Entit\xE4t einen Zustand hat, und liefert sie danach. Wirkung je Stufe: durchlassen, zur\xFCckhalten, verwerfen. Nach der H\xF6chstdauer geht alles wieder durch.",intro_settings:"Was jede Stufe ausl\xF6st, dazu Lampen, Alarm, Kn\xF6pfe auf dem Push und allgemeine Optionen. \xC4nderungen gelten erst nach \u201ESpeichern\u201C unten; die Test-Kn\xF6pfe nutzen den gespeicherten Stand.",drop_here:"Hierher ziehen",moved:"verschoben",tagline:"Alle Meldungen an einer Stelle",group_now:"Jetzt",group_now_sub:"was gerade ansteht",group_ops:"Betrieb",group_ops_sub:"wie die Anlage l\xE4uft",message_col:"Nachricht",since_col:"Seit",counter:"Z\xE4hler",cap_new:"{n} neu zu bewerten",cap_open:"{n} offen",drag_hint:"Ziehen, um die Gruppe zu wechseln",level_word:"Stufe",flow_title:"So l\xE4uft eine Meldung",flow_play:"Animation fortsetzen",flow_pause:"Animation anhalten",flow_s_in:"Eingang",flow_s_in_sub:"Automation, Skript",flow_s_kind:"Zuordnen",flow_s_kind_sub:"Meldungsart",flow_s_open:"Offen",flow_waiting:"wartet \xB7 {s} s",flow_s_rules:"Zustellregeln",flow_s_rules_short:"Regeln",flow_night_on:"Nachtmodus an",flow_night_off:"Nachtmodus aus",flow_s_out:"Empf\xE4nger",flow_s_out_sub:"Handy \xB7 Licht",flow_c_in:"Eine Automation schickt eine Meldung an notify.message_center.",flow_c_kind:"Die Zentrale ordnet sie einer Meldungsart zu: Stufe {n} \xB7 {name}. Unbekanntes kommt unter \u201ENeu, bitte bewerten\u201C.",flow_c_open:"Die Meldung ist offen und geht zu den Zustellregeln.",flow_c_rules_hold:"Die Regel \u201ENachtmodus\u201C ist aktiv und h\xE4lt Stufe {n} zur\xFCck.",flow_c_wait:"Zur\xFCck nach \u201EOffen\u201C mit dem Grund \u201Ezur\xFCckgehalten: Nachtmodus\u201C. Dort wartet sie, bis die Regel endet.",flow_c_night_off:"Der Nachtmodus endet. Wartende Meldungen werden neu bewertet.",flow_c_rules_free:"Keine Regel h\xE4lt sie mehr zur\xFCck.",flow_c_rules_pass:"Die Regel \u201ENachtmodus\u201C ist aktiv, l\xE4sst Stufe 3 aber durch.",flow_c_out_1:"Zugestellt. Stufe 1: Push aufs Handy.",flow_c_out_2:"Zugestellt. Stufe 2: Push und Lichtimpuls, die Lampe geht kurz aus und wieder an.",flow_c_out_3:"Zugestellt. Stufe 3: Alarm-Push mit Ton und Alarmlicht, bis jemand den Alarm beendet.",scan_button:"HA durchsuchen",scan_title:"Im Haus gefunden",scan_again:"Erneut suchen",scan_close:"Schlie\xDFen",scan_running:"Suche l\xE4uft \u2026",scan_head_todo:"{n} Stellen senden noch direkt. Diese Automationen, Skripte und Dateien m\xFCssen auf notify.message_center umgestellt werden.",scan_head_one:"1 Stelle sendet noch direkt. Sie muss auf notify.message_center umgestellt werden.",scan_head_done:"Keine Stelle sendet mehr direkt. Alles l\xE4uft \xFCber die Zentrale.",scan_searched:"Durchsucht: {a} Automationen, {s} Skripte, {f} Dateien.",scan_show_all:"Auch bereits umgestellte Stellen und Benachrichtigungen in der HA-Oberfl\xE4che zeigen ({n})",scan_automation:"Automation",scan_script:"Skript",scan_line:"Zeile",scan_open_editor:"Im Editor \xF6ffnen",scan_blueprint:"aus Blueprint {name}",scan_no_place:"Ort nicht bekannt (\xFCber die Oberfl\xE4che angelegt)",scan_direct:"sendet direkt",scan_center:"\xFCber die Zentrale",scan_persistent:"HA-Oberfl\xE4che",scan_target:"Ziel",scan_no_title:"ohne Titel",scan_first_line:"erste Zeile",scan_change_target:"\xC4ndern: Ziel durch notify.message_center ersetzen",scan_change_title:"und einen Titel erg\xE4nzen, zum Beispiel \u201E{title}\u201C",scan_change_title_free:"und einen Titel erg\xE4nzen",scan_title_computed:"Titel wird berechnet, Bedingung bitte selbst festlegen",scan_title_own:"Der Text beginnt nicht mit einer kurzen, festen \xDCberschrift. Titel und Bedingung bitte selbst festlegen",scan_kind:"Meldungsart",scan_files_title:"Weitere Fundstellen in Dateien",scan_files_note:"Zeilen au\xDFerhalb von Automationen und Skripten, die eine Benachrichtigung nennen. Dort bitte selbst nachsehen.",scan_limits:"Nicht einsehbar sind Integrationen, die selbst versenden, und Apps, deren Dateien au\xDFerhalb des Konfigurationsordners liegen.",scan_script_origin:"Skripte z\xE4hlen als die Automation, die sie startet. Die Meldungsart gilt deshalb f\xFCr jede Herkunft.",all_kinds:"Alle Meldungsarten",no_kind:"ohne Meldungsart",last_error:"letzter Fehler",no_error:"kein Fehler bekannt",tie:"Gleichstand mit {names}: die zuerst angelegte gewinnt",lights_always:"Davon auch blinken, wenn aus (kurz an und wieder aus)",lights_always_helper:"Nur Ziele aus der Liste oben. Alle anderen blinken nur, wenn sie gerade an sind.",effect_script_1:"Zus\xE4tzliches Skript bei Zustellung (Stufe 1)",effect_script_2:"Zus\xE4tzliches Skript bei Zustellung (Stufe 2)",effect_script_3:"Zus\xE4tzliches Skript bei Zustellung (Stufe 3)",effect_script_helper:"L\xE4uft einmal je Zustellung mit den Variablen title, text, origin, origin_name, kind, group, priority, count, message_id. Fehler stehen unter der Nachricht.",forward_script:"Skript f\xFCr \u201EAn KI\u201C",forward_script_helper:"L\xE4uft bei jedem \u201EAn KI\u201C (Handy, Seite, Aktion) mit title, text, note, origin, origin_name, kind, group, priority, message_id. Ohne Skript wird nur das Ereignis message_center_forwarded ausgel\xF6st.",ev_script:"Skript gelaufen",ev_script_failed:"Skript fehlgeschlagen",ev_script_skipped:"Skript \xFCbersprungen (Meldung aus eigener Wirkung)",test_script:"Skript {script}",test_script_failed:"Skript {script} fehlgeschlagen: {error}",rule_state_helper:"Vorschl\xE4ge aus dem aktuellen und den typischen Zust\xE4nden der Entit\xE4t; ein anderer Wert kann eingetippt werden."},_t={title:"Message Center",q_open:"\u201C",q_close:"\u201D",overview:"Overview",open:"Open",history:"History",kinds:"Message kinds",groups:"Groups",rules:"Delivery rules",recipients:"Recipients",ready:"Ready",not_ready:"Not ready",waiting:"Waiting",disturbed:"Disturbed",new:"New",active_rules:"Active rules",delivered_today:"Delivered today",last_delivery:"Last delivery",none_yet:"none yet",new_title:"New, please classify",new_empty:"No unclassified messages.",classify:"Classify",count:"Count",last_seen:"last",origin:"Origin",unknown_origin:"unknown origin",from_any:"any origin",open_empty:"Nothing open. Everything delivered.",send_now:"Send now",discard:"Discard",snooze:"Later",forward:"To assistant",state:"State",reason:"Reason",since:"since",until:"until",next_try:"next attempt",recipients_failed:"failed",history_empty:"Nothing in the history yet.",recent:"Recently ended",older:"Older",all_groups:"All groups",no_group:"no group",search:"Search",add_kind:"Add message kind",edit:"Edit",delete:"Delete",add_group:"Add group",add_rule:"Add delivery rule",save:"Save",cancel:"Cancel",confirm_delete:"Really delete?",name:"Name",title_mode:"Title condition",exact:"exactly",prefix:"starts with",contains:"contains",title_value:"Condition text",group:"Group",group_id:"Group",priority:"Priority",new_group:"Create new group",new_group_helper:"Fill in only when the group does not exist yet. It takes priority, spacing and expiry of this kind as its defaults.",required_missing:"Please fill in name and condition text.",unassigned:"Unassigned",defaults:"Defaults",group_empty:"No message kinds in this group yet.",unassigned_empty:"All message kinds are assigned to a group.",p1:"1 \xB7 Notice",p2:"2 \xB7 Important",p3:"3 \xB7 Alarm",no_hold:"Do not hold back",spacing:"Spacing (minutes, 0 = none)",expires_after:"Expiry (minutes, 0 = never)",light:"Light pulse",light_auto:"by priority",light_on:"always",light_off:"never",active:"Active",icon:"Icon (mdi:\u2026)",entity:"Entity",rule_state:"Entity state",effect_1:"Effect priority 1",effect_2:"Effect priority 2",effect_3:"Effect priority 3",pass:"pass",hold:"hold back",discard_effect:"discard",max_hours:"Maximum duration (hours)",current:"current",expired:"expired",unknown_state:"entity unknown",rule_inactive:"not active",kinds_empty:"No message kinds yet. Unclassified messages are on the overview.",groups_empty:"No groups yet.",rules_empty:'No delivery rules yet. A rule holds messages back while an entity is in a state, for example a helper "night mode" = on, and delivers them afterwards. Priority 3 (alarm) usually passes. Create the helper in HA first (Settings \u2192 Devices & services \u2192 Helpers \u2192 Toggle), then the rule here.',configured:"configured",available:"reachable",unavailable:"not reachable",recipients_hint:"A first phone is chosen when the integration is set up; after that recipients are managed here. New phones appear once their Companion App is set up.",minutes:"Minutes",note:"Note for the assistant",messages:"Messages",delivered:"delivered",failed:"failed",discarded:"discarded",unclear:"unclear",sending:"sending",retrying:"retrying",generation:"Generation",error:"Error",loading:"Loading \u2026",not_set_up:"Message Center is not set up.",text:"Text",labels:"Labels",kind:"Message kind",ev_snoozed:"snoozed",ev_forwarded:"forwarded to the assistant",ev_discarded:"discarded",ev_sent_now:"sent now",ev_light:"light pulse",ev_light_skipped:"light pulse skipped",ev_light_failed:"light pulse refused (no right to the lamps)",spacing_skip:"minimum spacing between light pulses",nothing_on:"no lamp on",effect_skip:"message from an own effect",pulse_ms:"Pulse length (milliseconds off)",light_spacing:"Minimum spacing between light pulses (seconds, 0 = none)",light_spacing_helper:"Against constant flicker when several priority-2 messages arrive in a row. Within the spacing the pulse is skipped and noted under the message. Tests ignore it.",test:"Test",test_hint:'"Test" sends a test message of this priority to all recipients: no history, no buttons, with the saved settings.',test_sent:"Test priority {n} sent to {names}",test_lights:"light pulse on {lights}",test_no_lights:"no light pulse (no chosen lamp is on)",test_failed:"not reached: {names}",confirm_alarm_test:"Really send an alarm test? It bypasses do not disturb and is loud.",src_phone:"from the phone",src_page:"on the page",src_action:"via action",src_center:"by the center",settings:"Settings",dismiss:"Dismiss",guide_title:"Welcome to the Message Center",guide_dismiss:"Got it, hide",guide_show:"Show the introduction again",guide_1:"Senders: automations and scripts call the action notify.message_center with title and text instead of the phone directly. The center handles the rest.",guide_2:'New, please classify: every new sort of message shows up on the overview. "Classify" turns it into a message kind with priority, group, spacing and expiry. Unclassified messages go out as priority 1.',guide_3:"Priorities: 1 notice = push. 2 important = push and a light pulse on chosen lamps. 3 alarm = push that bypasses do not disturb. Under Settings \u2192 Priority \u2192 effect, with test buttons.",guide_4:'Delivery rules: while an entity is in a state, for example a helper "night mode" = on, priorities 1 and 2 are held back and delivered afterwards. Alarm passes. Create the helper in HA first, then the rule on the Delivery rules tab.',guide_5:'Phone: "Later" snoozes a message, "To assistant" forwards it. Recipients and buttons are set under Recipients and Settings. The history shows everything that went through, with interventions.',kinds_one:"1 message kind",kinds_many:"{n} message kinds",levels_title:"Priority \u2192 effect",level_1_name:"Notice",level_1_effect:'Push to the phone. Held back while a delivery rule is active, unless the kind has "do not hold back".',level_2_name:"Important",level_2_effect:'Push to the phone plus a light pulse: the chosen lamps and switches go off and on again briefly, only those that are on (unless listed below under "also when off": then briefly on and off again). Length and minimum spacing are set below. The switch "Light pulse" on the device turns it off. Overridable per kind (always/never).',level_3_name:"Alarm",level_3_effect:`Push on the alarm channel: Android at full alarm volume with the device's alarm tone (changeable in Android settings under sounds), bypasses do not disturb; iPhone critical with sound (allow critical alerts in the app). Plus the alarm light: the chosen lamps and switches all go on and then toggle in step, all off, all on, until the alarm is ended, at the latest after the maximum duration. Then they return to their previous state. End it with the button "End alarm" on the push, the switch "Alarm" on the device, or at the top of this page.`,alarm_lights:"Lamps and switches for the alarm light",alarm_lights_helper:"Hue: pick single lamps, not rooms or zones. The Hue bridge accepts one command per second for groups and drops the rest.",alarm_interval_ms:"Alarm light interval (milliseconds; Zigbee lamps need about 1000)",alarm_channel:"Alarm channel on Android",alarm_channel_helper:`"Alarm stream" plays the system's default alarm tone at alarm volume; "max" the same at full volume, not on every device. "Own channel": set sound, vibration and the do-not-disturb exception once in Android under Notifications \u2192 Home Assistant \u2192 channel "message_center_alarm".`,alarm_channel_stream:"Alarm stream (default alarm tone)",alarm_channel_max:"Alarm stream, full volume",alarm_channel_own:"Own channel (set in Android)",alarm_tts:"Announcement: read the title aloud at full alarm volume (Android)",alarm_max_seconds:"Maximum duration of an alarm (seconds)",alarm_test_seconds:"Duration for a test (seconds)",alarm_active:"Alarm active",alarm_end:"End alarm",alarm_until:"until",ev_alarm_light:"alarm light",test_alarm:"alarm light on {lights}",lights:"Lamps and switches for the light pulse",lights_helper:"Empty = no light pulse. Whatever is on goes off for the length below and on again.",options_title:"Options",history_days:"Keep history (days)",sidebar:"Entry in the sidebar",hide_titles:"Do not write titles into history and attributes",allow_alarm:"Allow priority 3 (alarm) via the send action as well",silent_repeat:"Replace repeats silently (no sound, counter in the title only)",saved:"Saved.",used:"used",buttons_title:"Buttons on the push",buttons_intro:"The buttons reach HA only when the phone reaches HA: at home, via VPN or Nabu Casa.",button_snooze:'Button "Later" (snooze the message)',button_forward:'Button "To assistant" (forward the message, a note can be typed)',snooze_minutes:'Duration for "Later" (minutes)',snooze_minutes_2:'Second "Later" button with this duration (minutes, 0 = none)',snooze_input:"Type minutes instead of fixed buttons",snooze_input_helper:"Off: one tap, the duration is on the button. On: the phone asks for the minutes after the tap; empty = first duration.",recipients_intro:"Phones found with the Companion App. Checked ones receive the messages. At least one must be used.",at_least_one:"At least one recipient must be used.",intro_open:'Everything not through yet: waiting (rule, spacing, snoozed), sending, retrying after a failure, or unclear after a restart. "Send now" bypasses the rule, "Discard" ends the message without delivery.',intro_history:'What was delivered, discarded or failed, with interventions. "Recently ended" stays 24 hours in the working store, "Older" as long as chosen in the settings.',intro_kinds:"A message kind decides how one sort of message is handled: priority, group, spacing, expiry, light pulse. The most specific matching kind wins. Drag a kind into another group with the mouse.",intro_rules:"A rule holds messages back while an entity is in a state and delivers them afterwards. Effect per priority: pass, hold, discard. After the maximum duration everything passes again.",intro_settings:'What each priority triggers, plus lamps, alarm, buttons on the push and general options. Changes apply after "Save" at the bottom; the test buttons use the saved state.',drop_here:"Drop here",moved:"moved",tagline:"All messages in one place",group_now:"Now",group_now_sub:"what needs attention",group_ops:"Operation",group_ops_sub:"how the system runs",message_col:"Message",since_col:"Since",counter:"Count",cap_new:"{n} new to classify",cap_open:"{n} open",drag_hint:"Drag to change the group",level_word:"Priority",flow_title:"How a message travels",flow_play:"Resume animation",flow_pause:"Pause animation",flow_s_in:"Intake",flow_s_in_sub:"automation, script",flow_s_kind:"Assign",flow_s_kind_sub:"message kind",flow_s_open:"Open",flow_waiting:"waiting \xB7 {s} s",flow_s_rules:"Delivery rules",flow_s_rules_short:"Rules",flow_night_on:"night mode on",flow_night_off:"night mode off",flow_s_out:"Recipients",flow_s_out_sub:"phone \xB7 light",flow_c_in:"An automation sends a message to notify.message_center.",flow_c_kind:'The center assigns it to a message kind: priority {n} \xB7 {name}. Unknown ones show up under "New, please classify".',flow_c_open:"The message is open and goes to the delivery rules.",flow_c_rules_hold:'The rule "night mode" is active and holds priority {n} back.',flow_c_wait:'Back to "Open" with the reason "held back: night mode". It waits there until the rule ends.',flow_c_night_off:"Night mode ends. Waiting messages are evaluated again.",flow_c_rules_free:"No rule holds it back any more.",flow_c_rules_pass:'The rule "night mode" is active but lets priority 3 pass.',flow_c_out_1:"Delivered. Priority 1: push to the phone.",flow_c_out_2:"Delivered. Priority 2: push and a light pulse, the lamp goes off and on again briefly.",flow_c_out_3:"Delivered. Priority 3: alarm push with sound and the alarm light, until someone ends the alarm.",scan_button:"Search Home Assistant",scan_title:"Found in the house",scan_again:"Search again",scan_close:"Close",scan_running:"Searching \u2026",scan_head_todo:"{n} places still send directly. These automations, scripts and files need to be changed to notify.message_center.",scan_head_one:"1 place still sends directly. It needs to be changed to notify.message_center.",scan_head_done:"No place sends directly any more. Everything goes through the center.",scan_searched:"Searched: {a} automations, {s} scripts, {f} files.",scan_show_all:"Also show places already changed and notifications in the Home Assistant UI ({n})",scan_automation:"Automation",scan_script:"Script",scan_line:"line",scan_open_editor:"Open in the editor",scan_blueprint:"from blueprint {name}",scan_no_place:"place unknown (created in the UI)",scan_direct:"sends directly",scan_center:"through the center",scan_persistent:"Home Assistant UI",scan_target:"Target",scan_no_title:"no title",scan_first_line:"first line",scan_change_target:"Change: replace the target with notify.message_center",scan_change_title:'and add a title, for example "{title}"',scan_change_title_free:"and add a title",scan_title_computed:"The title is computed, please set the condition yourself",scan_title_own:"The text does not start with a short, fixed headline. Please choose title and condition yourself",scan_kind:"Message kind",scan_files_title:"More places in files",scan_files_note:"Lines outside automations and scripts that mention a notification. Please check these yourself.",scan_limits:"Not visible: integrations that send by themselves, and apps whose files live outside the configuration directory.",scan_script_origin:"Scripts count as the automation that starts them. The kind therefore applies to any origin.",all_kinds:"All message kinds",no_kind:"no message kind",last_error:"last error",no_error:"no error known",tie:"Tie with {names}: the one created first wins",lights_always:"Of these, also pulse when off (briefly on, then off again)",lights_always_helper:"Only targets from the list above. All others pulse only while they are on.",effect_script_1:"Extra script on delivery (priority 1)",effect_script_2:"Extra script on delivery (priority 2)",effect_script_3:"Extra script on delivery (priority 3)",effect_script_helper:"Runs once per delivery with the variables title, text, origin, origin_name, kind, group, priority, count, message_id. Failures are noted under the message.",forward_script:'Script for "To assistant"',forward_script_helper:'Runs on every "To assistant" (phone, page, action) with title, text, note, origin, origin_name, kind, group, priority, message_id. Without a script only the event message_center_forwarded fires.',ev_script:"script ran",ev_script_failed:"script failed",ev_script_skipped:"script skipped (message from an own effect)",test_script:"script {script}",test_script_failed:"script {script} failed: {error}",rule_state_helper:"Suggestions from the entity's current and typical states; another value can be typed."},ie=r=>{let s=r.startsWith("de")?mt:_t;return e=>s[e]??e};var Ge="318 61 900 900",je=["M742.1 114.1A41 41 0 0 1 793.9 114.1L991 274.5V211Q991 196 1006 196H1081Q1096 196 1096 211V359.9","L1188.6 435.2A41 41 0 0 1 1162.7 508H1135V740A75 75 0 0 1 1060 815H640L528 912","A22 22 0 0 1 491.6 895.4V815H479A75 75 0 0 1 404 740V508H373.3A41 41 0 0 1 347.4 435.2Z","M497 461V719H575V587L640 663L704 587V719H781V461H704L640 545L575 461Z","M1048 517A134 134 0 1 0 1048 663L984.6 621.7A58 58 0 1 1 984.6 558.3Z"].join("");var qe=(r=40,s=!0)=>l`<svg class="mc-logo" width=${r} height=${r} viewBox=${Ge} aria-hidden="true">
    <path fill="currentColor" fill-rule="evenodd" d=${je}></path>
    ${s?f`<circle cx="658" cy="368" r="40" fill="var(--primary-color)"></circle>
      <circle cx="768" cy="368" r="40" fill="var(--warning-color)"></circle>
      <circle cx="878" cy="368" r="40" fill="var(--error-color)"></circle>`:""}
  </svg>`;var w=class extends k{constructor(){super(...arguments);this.heading="";this.fields=[];this.data={};this.labels={};this._error="";this._busy=!1;this._data={};this._swallowKeys=e=>{e.stopPropagation()};this._close=()=>{this.dispatchEvent(new CustomEvent("editor-closed",{bubbles:!0,composed:!0}))};this._save=async()=>{this._busy=!0,this._error="";try{await this.onSave(this._data),this._close()}catch(e){this._error=e.message??String(e)}finally{this._busy=!1}}}willUpdate(e){e.has("data")&&(this._data=this.data)}static{this.styles=N`
    .error { color: var(--error-color); margin-top: 8px; }
    .fallback label { display: block; margin: 8px 0 4px; font-weight: 500; }
    .fallback input, .fallback select { width: 100%; padding: 8px; box-sizing: border-box; }
  `}connectedCallback(){super.connectedCallback(),this.addEventListener("keydown",this._swallowKeys)}disconnectedCallback(){super.disconnectedCallback(),this.removeEventListener("keydown",this._swallowKeys)}render(){let t=!!customElements.get("ha-form")?l`<ha-form
          .hass=${this.hass}
          .schema=${this.fields}
          .data=${this._data}
          .computeLabel=${n=>this.labels[n.name]??n.name}
          .computeHelper=${n=>this.helpers?.[n.name]}
          @value-changed=${n=>this._set(n.detail.value)}
        ></ha-form>`:this._fallbackForm(),i=l`
      ${t}
      ${this._error?l`<div class="error">${this._error}</div>`:d}
    `;return customElements.get("ha-dialog")?l`<ha-dialog .open=${!0} header-title=${this.heading} .preventScrimClose=${!0} @closed=${this._close}>
        ${i}
        <ha-button slot="footer" appearance="plain" @click=${this._close}>${this.t("cancel")}</ha-button>
        <ha-button slot="footer" .disabled=${this._busy} @click=${this._save}>${this.t("save")}</ha-button>
      </ha-dialog>`:l`<ha-card .header=${this.heading}>
      <div class="card-content">${i}</div>
      <div class="card-actions">
        <ha-button appearance="plain" @click=${this._close}>${this.t("cancel")}</ha-button>
        <ha-button .disabled=${this._busy} @click=${this._save}>${this.t("save")}</ha-button>
      </div>
    </ha-card>`}_set(e){let t=this._data;this._data=this.onChange?this.onChange(e,t):e}_fallbackForm(){return l`<div class="fallback">
      ${this.fields.map(e=>{let t=e.selector,i=this._data[e.name],n=a=>this._set({...this._data,[e.name]:a});return t.select?l`<label>${this.labels[e.name]??e.name}</label>
            <select @change=${a=>n(a.target.value)}>
              ${t.select.options?.map(a=>l`<option value=${a.value} ?selected=${a.value===i}>${a.label}</option>`)}
            </select>`:t.boolean?l`<label><input type="checkbox" ?checked=${!!i} @change=${a=>n(a.target.checked)} /> ${this.labels[e.name]??e.name}</label>`:t.number?l`<label>${this.labels[e.name]??e.name}</label>
            <input type="number" .value=${String(i??"")} min=${t.number.min??0} max=${t.number.max??99999} @input=${a=>n(Number(a.target.value))} />`:l`<label>${this.labels[e.name]??e.name}</label>
          <input type="text" .value=${String(i??"")} @input=${a=>n(a.target.value)} />`})}
    </div>`}};u([y({attribute:!1})],w.prototype,"hass",2),u([y({attribute:!1})],w.prototype,"t",2),u([y()],w.prototype,"heading",2),u([y({attribute:!1})],w.prototype,"fields",2),u([y({attribute:!1})],w.prototype,"data",2),u([y({attribute:!1})],w.prototype,"labels",2),u([y({attribute:!1})],w.prototype,"helpers",2),u([y({attribute:!1})],w.prototype,"onSave",2),u([y({attribute:!1})],w.prototype,"onChange",2),u([v()],w.prototype,"_error",2),u([v()],w.prototype,"_busy",2),u([v()],w.prototype,"_data",2);customElements.get("message-center-editor")||customElements.define("message-center-editor",w);var gt={w:720,h:148,xs:[72,216,360,504,648],y:44,bw:120,bh:80,ty:120,scale:1,sub:!0,font:13},ft={w:340,h:112,xs:[42,106,170,234,298],y:32,bw:58,bh:56,ty:88,scale:.8,sub:!1,font:10},Ve=2*Math.PI*19,Je="message_center_flow_paused",vt=()=>{try{return localStorage.getItem(Je)==="1"}catch{return!1}},bt=r=>{try{localStorage.setItem(Je,r?"1":"0")}catch{}},E=class extends k{constructor(){super(...arguments);this._level=1;this._i=0;this._paused=!1;this._compact=!1;this._count=0;this._toggle=()=>{this._paused=!this._paused,bt(this._paused),!this._paused&&this._timer===void 0&&this._advance()}}static{this.styles=N`
    :host { display: block; padding: 12px 16px 14px; }
    .head { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 10px; margin-bottom: 6px; }
    .head .title { font-size: 16px; font-weight: 500; flex: 1 1 auto; }
    .head.compact .title { flex-basis: 100%; }
    .head.compact button.ctl { margin-left: auto; }
    .lv { font-size: 12px; padding: 1px 9px; border-radius: 10px; border: 1px solid var(--divider-color);
      color: var(--secondary-text-color); transition: background .3s, color .3s; white-space: nowrap; }
    .lv.on.p1 { background: var(--primary-color); color: #fff; border-color: transparent; }
    .lv.on.p2 { background: var(--warning-color); color: #000; border-color: transparent; }
    .lv.on.p3 { background: var(--error-color); color: #fff; border-color: transparent; }
    button.ctl { border: 0; background: transparent; color: var(--secondary-text-color); cursor: pointer; padding: 4px;
      border-radius: 50%; display: inline-flex; }
    button.ctl:hover { background: var(--secondary-background-color); color: var(--primary-text-color); }
    svg.stage { display: block; width: 100%; height: auto; margin: 0 auto; }
    svg.stage.compact { max-width: 440px; }
    .caption { min-height: 2.8em; margin-top: 4px; font-size: 14px; line-height: 1.4; color: var(--primary-text-color); text-align: center; }
    .track { stroke: var(--divider-color); stroke-width: 2; stroke-dasharray: 2 6; stroke-linecap: round; fill: none; }
    .stop { fill: var(--divider-color); }
    .station rect { fill: var(--secondary-background-color, rgba(127,127,127,.08)); stroke: var(--divider-color); stroke-width: 1.5;
      transition: stroke .3s, stroke-width .3s; }
    .station.active rect { stroke: var(--primary-color); stroke-width: 2.5; }
    .station text { text-anchor: middle; fill: var(--primary-text-color); font-family: inherit; }
    .station text.label { font-weight: 500; }
    .station text.sub { fill: var(--secondary-text-color); font-size: 10.5px; }
    .ico { fill: none; stroke: var(--secondary-text-color); stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
    .station.active .ico { stroke: var(--primary-text-color); }
    .moon { transition: fill .5s, stroke .5s; }
    .moon.on { fill: #f5c542; stroke: #f5c542; }
    .glow { fill: #f5c542; stroke: #f5c542; transition: opacity .2s; }
    .dot { fill: var(--error-color); stroke: none; opacity: 0; }
    .token { transition: transform .9s cubic-bezier(.4, 0, .2, 1), opacity .35s; }
    .token.hidden { opacity: 0; transition: none; }
    .token .env { stroke: none; }
    .token.lvl1 .env { fill: var(--primary-color); }
    .token.lvl2 .env { fill: var(--warning-color); }
    .token.lvl3 .env { fill: var(--error-color); }
    .token .flap { fill: none; stroke: #fff; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
    .token.lvl2 .flap { stroke: #000; }
    .token .ring { fill: none; stroke: var(--primary-text-color); stroke-width: 2.5; stroke-linecap: round;
      stroke-dasharray: ${Ve}; animation: drain linear forwards; }
    @keyframes drain { from { stroke-dashoffset: 0; } to { stroke-dashoffset: ${Ve}; } }
    .fx { transform-box: fill-box; transform-origin: center; }
    .phone.ring1 .fx, .phone.ring2 .fx { animation: wiggle .45s ease-in-out .5s 3; }
    .phone.ring3 .fx { animation: wiggle .3s ease-in-out .5s 9; }
    .phone.ring1 .dot, .phone.ring2 .dot, .phone.ring3 .dot { animation: pop .3s ease-out .5s forwards; }
    @keyframes wiggle { 0%, 100% { transform: rotate(0); } 25% { transform: rotate(-14deg); } 75% { transform: rotate(14deg); } }
    @keyframes pop { to { opacity: 1; } }
    .lamp.ring2 .glow { animation: pulse 1.5s linear .9s 1; }
    .lamp.ring3 .glow { animation: alarm .6s steps(1) .9s 5; }
    @keyframes pulse { 0%, 15% { opacity: 1; } 22%, 62% { opacity: .08; } 70%, 100% { opacity: 1; } }
    @keyframes alarm { 0% { opacity: .08; } 50% { opacity: 1; } }
    @media (prefers-reduced-motion: reduce) { .token { transition: opacity .35s; } }
  `}connectedCallback(){super.connectedCallback(),this._resize=new ResizeObserver(e=>{let t=e[0]?.contentRect.width??0;t&&(this._compact=t<560)}),this._resize.observe(this),vt()||window.matchMedia?.("(prefers-reduced-motion: reduce)").matches?(this._paused=!0,this._level=2,this._i=this._steps(2).findIndex(e=>e.wait)):this._enter(0)}disconnectedCallback(){super.disconnectedCallback(),this._resize?.disconnect(),this._clear()}_clear(){window.clearTimeout(this._timer),window.clearInterval(this._tick),this._timer=void 0,this._tick=void 0}_steps(e){let t=this.t,i=p=>t(p).replace("{n}",String(e)).replace("{name}",t(`level_${e}_name`)),n=[{at:0,text:"",ms:500,night:!0,hidden:!0},{at:0,text:i("flow_c_in"),ms:2400,night:!0},{at:1,text:i("flow_c_kind"),ms:3200,night:!0},{at:2,text:i("flow_c_open"),ms:2e3,night:!0}],a=[{at:4,text:i(`flow_c_out_${e}`),ms:e===3?4800:4e3,night:e===3,effect:!0},{at:4,text:"",ms:500,night:e===3,hidden:!0}];return e===3?[...n,{at:3,text:i("flow_c_rules_pass"),ms:3e3,night:!0},...a]:[...n,{at:3,text:i("flow_c_rules_hold"),ms:3e3,night:!0},{at:2,text:i("flow_c_wait"),ms:4e3,night:!0,wait:!0},{at:2,text:i("flow_c_night_off"),ms:2600,night:!1},{at:3,text:i("flow_c_rules_free"),ms:2200,night:!1},...a]}_enter(e){this._clear(),this._i=e;let t=this._steps(this._level)[e];t.wait&&(this._count=Math.ceil(t.ms/1e3),this._tick=window.setInterval(()=>{this._count>1&&(this._count-=1)},1e3)),this._timer=window.setTimeout(()=>{this._paused?this._timer=void 0:this._advance()},t.ms)}_advance(){let e=this._steps(this._level);this._i+1<e.length?this._enter(this._i+1):(this._level=this._level%3+1,this._enter(0))}render(){let e=this.t,t=this._compact?ft:gt,i=this._steps(this._level)[this._i],n=i.effect?`ring${this._level}`:"",a=[f`<rect class="ico" x="-11" y="-8" width="22" height="16" rx="2"></rect><polyline class="ico" points="-11,-7 0,2 11,-7"></polyline>`,f`<path class="ico" d="M-10 -8 H2 L11 0 L2 8 H-10 Z"></path><circle class="ico" cx="-5" cy="0" r="1.6"></circle>`,f`<path class="ico" d="M-11 -1 L-7 -9 H7 L11 -1 V8 H-11 Z"></path><path class="ico" d="M-11 -1 H-4 Q-4 3 0 3 Q4 3 4 -1 H11"></path>`,f`<path class="ico moon ${i.night?"on":""}" d="M3 -10 A10 10 0 1 0 10 4 A8.5 8.5 0 0 1 3 -10 Z"></path>`,f`<g transform="translate(-13 0)" class="phone ${n}"><g class="fx">
            <rect class="ico" x="-6" y="-11" width="12" height="22" rx="2.5"></rect><path class="ico" d="M-2 7.5 H2"></path>
            <circle class="dot" cx="6" cy="-10" r="3.6"></circle></g></g>
          <g transform="translate(13 0)" class="lamp ${n}">
            <circle class="ico glow" cx="0" cy="-3" r="6.5"></circle><path class="ico" d="M-3 5.5 H3 M-2 8.5 H2"></path></g>`],p=["flow_s_in","flow_s_kind","flow_s_open",this._compact?"flow_s_rules_short":"flow_s_rules","flow_s_out"].map(c=>e(c)),o=[e("flow_s_in_sub"),e("flow_s_kind_sub"),i.wait?e("flow_waiting").replace("{s}",String(this._count)):"",i.night?e("flow_night_on"):e("flow_night_off"),e("flow_s_out_sub")],m=c=>f`<g class="station ${!i.hidden&&i.at===c?"active":""}">
      <rect x=${t.xs[c]-t.bw/2} y=${t.y-t.bh/2} width=${t.bw} height=${t.bh} rx="12"></rect>
      <g transform="translate(${t.xs[c]} ${t.y-(t.sub?16:9)}) scale(${t.scale})">${a[c]}</g>
      <text class="label" x=${t.xs[c]} y=${t.y+(t.sub?12:20)} font-size=${t.font}>${p[c]}</text>
      ${t.sub?f`<text class="sub" x=${t.xs[c]} y=${t.y+28}>${o[c]}</text>`:d}
    </g>`;return l`
      <div class="head ${this._compact?"compact":""}">
        <span class="title">${e("flow_title")}</span>
        ${[1,2,3].map(c=>l`<span class="lv p${c} ${c===this._level?"on":""}">${c} · ${e(`level_${c}_name`)}</span>`)}
        <button class="ctl" @click=${this._toggle} title=${this._paused?e("flow_play"):e("flow_pause")} aria-label=${this._paused?e("flow_play"):e("flow_pause")}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">${this._paused?f`<path d="M8 5v14l11-7z"></path>`:f`<path d="M6 5h4v14H6zM14 5h4v14h-4z"></path>`}</svg>
        </button>
      </div>
      <svg class="stage ${this._compact?"compact":""}" viewBox="0 0 ${t.w} ${t.h}" role="img" aria-label=${e("flow_title")}>
        <path class="track" d="M${t.xs[0]} ${t.ty} H${t.xs[4]}"></path>
        ${t.xs.map(c=>f`<circle class="stop" cx=${c} cy=${t.ty} r="3"></circle>`)}
        ${[0,1,2,3,4].map(m)}
        <g class="token lvl${this._level} ${i.hidden?"hidden":""}" style="transform: translate(${t.xs[i.at]}px, ${t.ty}px)">
          <g transform="scale(${t.scale})">
            ${i.wait?f`<circle class="ring" r="19" transform="rotate(-90)" style="animation-duration: ${i.ms}ms"></circle>`:d}
            <rect class="env" x="-14" y="-10" width="28" height="20" rx="3"></rect>
            <polyline class="flap" points="-13,-9 0,1.5 13,-9"></polyline>
          </g>
        </g>
      </svg>
      <div class="caption">${i.text||l`&nbsp;`}</div>
    `}};u([y({attribute:!1})],E.prototype,"t",2),u([v()],E.prototype,"_level",2),u([v()],E.prototype,"_i",2),u([v()],E.prototype,"_paused",2),u([v()],E.prototype,"_compact",2),u([v()],E.prototype,"_count",2);customElements.get("message-center-flow")||customElements.define("message-center-flow",E);var yt={grid:f`<rect x="4" y="4" width="7" height="7" rx="1.5"></rect><rect x="13" y="4" width="7" height="7" rx="1.5"></rect><rect x="4" y="13" width="7" height="7" rx="1.5"></rect><rect x="13" y="13" width="7" height="7" rx="1.5"></rect>`,inbox:f`<path d="M4 13l2.5-7.5h11L20 13v5a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 18z"></path><path d="M4 13h4.5l1 2.5h5l1-2.5H20"></path>`,history:f`<path d="M3.5 12a8.5 8.5 0 1 0 2.7-6.2L3.5 8.3"></path><path d="M3.5 3.8v4.5H8"></path><path d="M12 7.5V12l3.2 1.9"></path>`,tag:f`<path d="M4 4.5h7.2l8.3 8.3a1.6 1.6 0 0 1 0 2.3l-4.9 4.9a1.6 1.6 0 0 1-2.3 0L4 11.7z"></path><circle cx="8" cy="8.5" r="1.2"></circle>`,moon:f`<path d="M20 14.5A8 8 0 1 1 9.5 4a7.5 7.5 0 0 0 10.5 10.5z"></path>`,phone:f`<rect x="7" y="3" width="10" height="18" rx="2.2"></rect><path d="M11 17.8h2"></path>`,sliders:f`<path d="M4 6h8M16 6h4M4 12h2M10 12h10M4 18h10M18 18h2"></path><circle cx="14" cy="6" r="2"></circle><circle cx="8" cy="12" r="2"></circle><circle cx="16" cy="18" r="2"></circle>`,clock:f`<circle cx="12" cy="12" r="9"></circle><path d="M12 7v5l3 2"></path>`,retry:f`<path d="M20 11a8 8 0 0 0-14.5-3.5"></path><path d="M4 4v4h4"></path><path d="M4 13a8 8 0 0 0 14.5 3.5"></path><path d="M20 20v-4h-4"></path>`,check:f`<circle cx="12" cy="12" r="9"></circle><path d="M8 12.5l2.8 2.8L16 9.5"></path>`,tick:f`<path d="M5.5 12.5l4.2 4.2 8.8-9.4"></path>`,ban:f`<circle cx="12" cy="12" r="9"></circle><path d="M5.6 5.6l12.8 12.8"></path>`,alert:f`<path d="M12 4l9 16H3z"></path><path d="M12 10v4.5M12 17.2v.3"></path>`,send:f`<path d="M21 3L10 14"></path><path d="M21 3l-7 18-4-7-7-4z"></path>`,search:f`<circle cx="11" cy="11" r="6.5"></circle><path d="M16 16l4.5 4.5"></path>`,file:f`<path d="M6 3.5h8l4 4V20.5H6z"></path><path d="M14 3.5v4h4"></path>`,chev:f`<path d="M9 6l6 6-6 6"></path>`,grip:f`<circle cx="9" cy="6" r=".7"></circle><circle cx="15" cy="6" r=".7"></circle><circle cx="9" cy="12" r=".7"></circle><circle cx="15" cy="12" r=".7"></circle><circle cx="9" cy="18" r=".7"></circle><circle cx="15" cy="18" r=".7"></circle>`,pause:f`<path d="M9 5v14M15 5v14"></path>`,arrow:f`<path d="M4 12h15M13 6l6 6-6 6"></path>`,trash:f`<path d="M4 7h16M9 7V4h6v3M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M10 11v6M14 11v6"></path>`},A=(r,s=20,e=1.8)=>l`<svg class="ico" width=${s} height=${s} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    stroke-width=${e} stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${yt[r]??d}</svg>`;var wt=["overview","open","history","kinds","rules","recipients","settings"],xt={overview:"grid",open:"inbox",history:"history",kinds:"tag",rules:"moon",recipients:"phone",settings:"sliders"},$t={waiting:"clock",sending:"send",retrying:"retry",unclear:"alert",delivered:"check",failed:"alert",discarded:"ban"},kt={hold:"pause",pass:"arrow",discard:"trash"},b=class extends k{constructor(){super(...arguments);this.narrow=!1;this._tab="overview";this._error="";this._filterGroup="";this._filterKind="";this._search="";this._settingsNote="";this._testNote="";this._dragKind="";this._dropTarget="";this._openRows=new Set;this._scanBusy=!1;this._scanAll=!1;this._t=ie("en");this._lang="";this._runScan=async()=>{this._scanBusy=!0;try{this._scan=await Fe(this.hass),this._error=""}catch(e){this._error=String(e.message??e)}finally{this._scanBusy=!1}};this._alarmOff=async()=>{try{await We(this.hass)}catch(e){this._error=String(e.message??e)}};this._saveSettings=async()=>{let e=this._settings;if(e)try{let t=await ge(this.hass,{guide_dismissed:this._config?.options.guide_dismissed??!1,history_days:Number(e.history_days??30),sidebar:e.sidebar!==!1,hide_titles:!!e.hide_titles,allow_alarm:!!e.allow_alarm,lights:e.lights??[],pulse_ms:Number(e.pulse_ms??500),light_spacing:Number(e.light_spacing??0),alarm_lights:e.alarm_lights??[],alarm_interval_ms:Number(e.alarm_interval_ms??1e3),alarm_max_seconds:Number(e.alarm_max_seconds??300),alarm_test_seconds:Number(e.alarm_test_seconds??5),silent_repeat:!!e.silent_repeat,alarm_channel:String(e.alarm_channel??"alarm_stream"),alarm_tts:!!e.alarm_tts,button_snooze:e.button_snooze!==!1,button_forward:e.button_forward!==!1,snooze_minutes:Number(e.snooze_minutes??30),snooze_minutes_2:Number(e.snooze_minutes_2??0),snooze_input:!!e.snooze_input,lights_always:e.lights_always??[],forward_script:e.forward_script||null,effect_script_1:e.effect_script_1||null,effect_script_2:e.effect_script_2||null,effect_script_3:e.effect_script_3||null});this._settings={...this._optionsWithDefaults(),...t.options},this._settingsNote=this._t("saved"),this._error=""}catch(t){this._error=String(t.message??t)}}}static{this.styles=N`
    :host { display: block; height: 100%; container-type: inline-size;
      background: var(--primary-background-color); color: var(--primary-text-color);
      /* state colours as text: mixed with the text colour so that they stay readable on light and dark cards */
      --mc-warn: color-mix(in srgb, var(--warning-color) 62%, var(--primary-text-color));
      --mc-bad: color-mix(in srgb, var(--error-color) 70%, var(--primary-text-color));
      --mc-good: color-mix(in srgb, var(--success-color, #43a047) 70%, var(--primary-text-color)); }
    .ico { flex: none; display: block; }
    /* Head: the band is a speech bubble like the logo: round lower corners and a tail under the logo,
       with a thin lighter line along its lower edge. */
    header { position: relative; padding: 0 0 20px; background: var(--card-background-color);
      --mc-band: color-mix(in srgb, var(--primary-color) 64%, #000);
      --mc-line: color-mix(in srgb, var(--primary-color) 70%, #fff); }
    header .bubble { position: relative; display: flex; align-items: center; gap: 14px; min-height: 88px; box-sizing: border-box;
      padding: 10px 20px 10px 64px; border-radius: 0 0 24px 24px; color: #fff;
      background: linear-gradient(color-mix(in srgb, var(--primary-color) 84%, #000), var(--mc-band)); box-shadow: 0 4px 0 var(--mc-line); }
    header ha-menu-button { position: absolute; left: 8px; top: 50%; transform: translateY(-50%); color: #fff; }
    header .mc-logo { color: #fff; flex: none; }
    header .titles { min-width: 0; }
    header h1 { font-size: 28px; font-weight: 300; line-height: 1.15; margin: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    header h1 b { font-weight: 600; }
    header .tag { margin-top: 2px; font-size: 13px; color: rgba(255, 255, 255, .88); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    header .ready { margin-left: auto; flex: none; display: inline-flex; align-items: center; gap: 7px;
      padding: 3px 11px 3px 4px; border-radius: 13px; background: rgba(255, 255, 255, .2); font-size: 13px; font-weight: 500; line-height: 1.3; }
    header .ready .led { display: grid; place-items: center; width: 18px; height: 18px; border-radius: 50%; background: var(--success-color, #43a047); }
    header .ready.off .led { background: var(--error-color); }
    /* the tail: same fill as the band's lower edge; its outline continues the lighter line */
    header .tail { position: absolute; left: 74px; top: 88px; width: 38px; height: 22px; display: block; overflow: hidden; }
    header .tail path { fill: var(--mc-band); stroke: var(--mc-line); stroke-width: 8; stroke-linejoin: round; paint-order: stroke; }
    /* Tabs: icon and name; on narrow screens the seven icons only, the active name in a line below. */
    nav { display: flex; align-items: stretch; gap: 4px; padding: 0 10px; overflow-x: auto; scrollbar-width: none;
      background: var(--card-background-color); border-bottom: 1px solid var(--divider-color); }
    nav::-webkit-scrollbar { display: none; }
    nav button { position: relative; display: inline-flex; align-items: center; gap: 8px; flex: none; padding: 11px 12px; border: 0;
      background: none; color: var(--secondary-text-color); font: inherit; line-height: 20px; white-space: nowrap; cursor: pointer; }
    nav button.active { color: var(--primary-text-color); font-weight: 500; }
    nav button.active .ico { color: color-mix(in srgb, var(--primary-color) 72%, var(--primary-text-color)); }
    nav button.active::after { content: ""; position: absolute; left: 10px; right: 10px; bottom: 0; height: 3px;
      border-radius: 3px 3px 0 0; background: var(--primary-color); }
    nav .ib { position: relative; display: inline-flex; }
    nav .cnt { box-sizing: border-box; min-width: 18px; height: 18px; padding: 0 5px; border-radius: 9px; font-size: 11.5px; font-weight: 500;
      line-height: 18px; text-align: center; background: color-mix(in srgb, var(--primary-color) 24%, transparent); color: var(--primary-text-color); }
    nav .ib .cnt { display: none; }
    .navcap { display: none; }
    main { padding: 16px; max-width: 1100px; margin: 0 auto; box-sizing: border-box; }
    /* Overview: two groups of numbers, "now" and "operation", each with a coloured top edge for its state. */
    .groups { display: grid; grid-template-columns: minmax(0, 4fr) minmax(0, 3fr); gap: 12px; margin-bottom: 16px; }
    .kgroup { min-width: 0; padding: 14px 4px 12px; background: var(--card-background-color); border: 1px solid var(--divider-color);
      border-radius: var(--ha-card-border-radius, 12px); overflow: hidden; box-shadow: inset 0 3px 0 var(--divider-color); }
    .kgroup.warn { box-shadow: inset 0 3px 0 var(--warning-color); }
    .kgroup.bad { box-shadow: inset 0 3px 0 var(--error-color); }
    .kgroup.good { box-shadow: inset 0 3px 0 var(--success-color, #43a047); }
    .kgroup h2 { margin: 0 0 10px; padding: 0 12px; font-size: 12px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; }
    .kgroup h2 span { margin-left: 6px; font-weight: 400; letter-spacing: 0; text-transform: none; color: var(--secondary-text-color); }
    .kpis { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(0, 1fr); }
    .kpi { padding: 2px 12px; border-left: 1px solid var(--divider-color); min-width: 0; }
    .kpi:first-child { border-left: 0; }
    .kpi .value { font-size: 28px; font-weight: 500; line-height: 1.1; }
    .kpi .label { color: var(--secondary-text-color); font-size: 13px; margin-top: 4px; }
    .kpi.warn .value { color: var(--mc-warn); }
    .kpi.bad .value { color: var(--mc-bad); }
    .kpi.good .value { color: var(--mc-good); }
    .kpi.zero .value { color: var(--secondary-text-color); }
    .pair { display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); gap: 0 12px; align-items: start; }
    /* Messages: a compact table, one line per message; a click unfolds text, reason, events and buttons. */
    .mtable .thead, .mtable summary { display: grid; grid-template-columns: 34px 128px minmax(0, 1fr) minmax(0, 240px) 92px 18px;
      column-gap: 12px; align-items: center; padding: 0 12px 0 14px; }
    .mtable .thead { height: 32px; font-size: 12px; color: var(--secondary-text-color); border-bottom: 1px solid var(--divider-color); }
    .mtable details { border-top: 1px solid var(--divider-color); --st: var(--secondary-text-color); --lvl: var(--primary-color); --lvl-on: #fff; }
    .mtable .thead + details { border-top: 0; }
    .mtable summary { min-height: 44px; cursor: pointer; list-style: none; }
    .mtable summary::-webkit-details-marker { display: none; }
    .mtable summary:hover, .mtable details[open] { background: color-mix(in srgb, var(--primary-text-color) 5%, transparent); }
    .mtable details.s-wait { --st: var(--warning-color); }
    .mtable details.s-fail { --st: var(--error-color); }
    .mtable details.s-ok { --st: var(--success-color, #43a047); }
    .mtable details.l2, .fx-i.l2 { --lvl: var(--warning-color); --lvl-on: #000; }
    .mtable details.l3, .fx-i.l3 { --lvl: var(--error-color); --lvl-on: #fff; }
    .lvbox { display: grid; place-items: center; width: 22px; height: 22px; border-radius: 6px; background: var(--lvl, var(--primary-color));
      color: var(--lvl-on, #fff); font-size: 13px; font-weight: 600; line-height: 1; flex: none; }
    .stc { display: flex; align-items: center; gap: 6px; min-width: 0; font-size: 13px; font-weight: 500;
      color: color-mix(in srgb, var(--st) 55%, var(--primary-text-color)); }
    .stc span, .why b { text-transform: lowercase; }
    .line { display: flex; align-items: baseline; gap: 8px; min-width: 0; white-space: nowrap; }
    .line .title { flex: 0 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; font-weight: 500; }
    .line .cnt { flex: none; font-size: 12px; font-weight: 500; padding: 0 7px; border-radius: 9px; background: var(--secondary-background-color); }
    .snip { flex: 1 1 0; min-width: 0; overflow: hidden; text-overflow: ellipsis; color: var(--secondary-text-color); }
    .org { min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 13px; color: var(--secondary-text-color); }
    .time { text-align: right; font-size: 13px; font-variant-numeric: tabular-nums; color: var(--secondary-text-color); white-space: nowrap; }
    .chev { display: inline-flex; color: var(--secondary-text-color); transition: transform .15s; }
    details[open] > summary .chev { transform: rotate(90deg); }
    .more { display: flex; flex-wrap: wrap; gap: 12px 32px; padding: 4px 16px 14px 60px; }
    .more-l { flex: 1 1 280px; min-width: 0; }
    .more .text { white-space: pre-wrap; word-break: break-word; }
    .why { display: flex; align-items: flex-start; gap: 6px; margin-top: 6px; font-size: 13px; overflow-wrap: anywhere;
      color: color-mix(in srgb, var(--st) 55%, var(--primary-text-color)); }
    .why .ico { margin-top: 2px; }
    .why b { font-weight: 600; }
    .fail { color: var(--mc-bad); }
    .more .events { margin-top: 8px; font-size: 12px; color: var(--secondary-text-color); border-left: 2px solid var(--divider-color); padding-left: 8px; }
    .more .actions { justify-content: flex-start; margin: 8px 0 0 -8px; gap: 2px; }
    .dl { flex: 0 1 330px; display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: 3px 14px; align-content: start; margin: 0; font-size: 13px; }
    .dl dt { color: var(--secondary-text-color); }
    .dl dd { margin: 0; overflow-wrap: anywhere; }
    /* Search over the house: places that notify, grouped by automation or script. */
    .scan-ico { display: inline-flex; flex: none; color: var(--primary-color); }
    .scan code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12.5px; overflow-wrap: anywhere; }
    .scan-head { margin: 0 16px 10px; padding: 10px 12px; border-radius: 8px; font-weight: 500; line-height: 1.4;
      background: color-mix(in srgb, var(--warning-color) 16%, transparent); border: 1px solid color-mix(in srgb, var(--warning-color) 45%, transparent); }
    .scan-head.done { background: color-mix(in srgb, var(--success-color, #43a047) 16%, transparent);
      border-color: color-mix(in srgb, var(--success-color, #43a047) 45%, transparent); }
    .scan-all { display: flex; gap: 8px; align-items: center; padding: 0 16px 12px; font-size: 13px; color: var(--secondary-text-color); cursor: pointer; }
    .scan-src { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 10px; padding: 10px 16px; border-top: 1px solid var(--divider-color);
      background: color-mix(in srgb, var(--primary-text-color) 4%, transparent); }
    .scan-src b { font-weight: 500; font-size: 15px; }
    .scan-src .where { color: var(--secondary-text-color); font-size: 13px; }
    .scan-src a { font-size: 13px; margin-left: auto; }
    .scan-todo { color: var(--mc-warn); }
    .scan-note { padding: 8px 16px 12px; color: var(--secondary-text-color); font-size: 13px; }
    .chip.scan-direct { background: var(--warning-color); color: #000; }
    .chip.scan-center { background: var(--success-color, #43a047); color: #fff; }
    /* Kinds and rules: grip for dragging, effect per priority as three small fields. */
    .grip { display: inline-grid; place-items: center; flex: none; align-self: center; color: var(--secondary-text-color); cursor: grab; opacity: .75; }
    .fx { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 7px; }
    .fx-i { display: inline-flex; align-items: center; gap: 6px; padding: 3px 9px 3px 4px; border-radius: 8px; font-size: 13px;
      --lvl: var(--primary-color); --lvl-on: #fff;
      background: color-mix(in srgb, var(--lvl) 14%, transparent); border: 1px solid color-mix(in srgb, var(--lvl) 40%, transparent); }
    .fx-i .lvbox { width: 20px; height: 20px; font-size: 12px; font-weight: 700; }
    /* Seven tabs with names need about 900 px. Below that: icons only, the active name in a line below. */
    @container (max-width: 920px) {
      nav { gap: 0; padding: 0 4px; }
      nav button { flex: 1 1 0; justify-content: center; padding: 12px 0; }
      nav .lbl, nav button > .cnt { display: none; }
      nav .ib .cnt { display: block; position: absolute; top: -6px; right: -9px; min-width: 16px; height: 16px; padding: 0 4px; border-radius: 8px;
        font-size: 10.5px; font-weight: 600; line-height: 16px; background: var(--primary-color); color: #fff;
        box-shadow: 0 0 0 2px var(--card-background-color); }
      .navcap { display: block; padding: 7px 16px; border-bottom: 1px solid var(--divider-color); background: var(--card-background-color);
        font-size: 13px; color: var(--secondary-text-color); }
      .navcap b { font-weight: 500; color: var(--primary-text-color); }
    }
    @container (max-width: 600px) {
      header { padding-bottom: 17px; }
      header .bubble { gap: 10px; min-height: 64px; padding: 8px 12px 8px 50px; border-radius: 0 0 18px 18px; box-shadow: 0 3px 0 var(--mc-line); }
      header ha-menu-button { left: 4px; }
      header h1 { font-size: 20px; }
      header .mc-logo { width: 40px; height: 40px; }
      header .tag { display: none; }
      header .tail { left: 55px; top: 64px; width: 30px; height: 18px; }
      header .tail path { stroke-width: 6; }
      .groups, .pair { grid-template-columns: minmax(0, 1fr); }
      .kpi { padding: 2px 10px; }
      .kpi .value { font-size: 24px; }
      .kpi .label { font-size: 12px; }
      .mtable .thead { display: none; }
      .mtable details:first-of-type { border-top: 0; }
      .mtable summary { grid-template-columns: 22px 18px minmax(0, 1fr) auto 18px; column-gap: 8px; align-items: start; padding: 10px 10px 10px 12px; }
      .stc { padding-top: 2px; }
      .stc span, .org { display: none; }
      .line { flex-wrap: wrap; gap: 0 6px; }
      .line .title { max-width: 100%; }
      .snip { flex: 1 1 100%; }
      .time { padding-top: 2px; }
      .chev { margin-top: 2px; }
      .more { padding: 2px 12px 12px 12px; }
    }
    ha-card { margin-bottom: 16px; }
    /* Rows and group heads wrap on narrow screens: text keeps a readable width, buttons drop below. */
    .row { display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: flex-start; padding: 12px 16px; border-top: 1px solid var(--divider-color); }
    .row:first-of-type { border-top: 0; }
    .row .body { flex: 1 1 16em; min-width: 0; }
    .row .title { font-weight: 500; }
    .row .meta { color: var(--secondary-text-color); font-size: 13px; margin-top: 2px; word-break: break-word; }
    .row .text { margin-top: 4px; white-space: pre-wrap; word-break: break-word; }
    .row .events { margin-top: 6px; font-size: 12px; color: var(--secondary-text-color); border-left: 2px solid var(--divider-color); padding-left: 8px; }
    .actions { display: flex; flex-wrap: wrap; gap: 4px; justify-content: flex-end; margin-left: auto; }
    .group-head { display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: center; padding: 12px 16px; }
    .group-head ha-icon { color: var(--primary-color); flex: none; }
    .group-head .body { flex: 1 1 14em; min-width: 0; }
    .group-head .title { font-size: 16px; font-weight: 500; }
    .group-head .meta { color: var(--secondary-text-color); font-size: 13px; margin-top: 2px; word-break: break-word; }
    .chip { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 12px; margin-right: 4px;
      background: var(--secondary-background-color); color: var(--primary-text-color); }
    .chip.p1 { background: var(--primary-color); color: #fff; }
    .chip.p2 { background: var(--warning-color); color: #000; }
    .chip.p3 { background: var(--error-color); color: #fff; }
    .chip.state-waiting, .chip.state-retrying, .chip.state-unclear { background: var(--warning-color); color: #000; }
    .chip.state-failed { background: var(--error-color); color: #fff; }
    .chip.state-delivered { background: var(--success-color, #43a047); color: #fff; }
    .alarm-bar { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; padding: 10px 16px; margin-bottom: 12px;
      background: var(--error-color); color: #fff; border-radius: var(--ha-card-border-radius, 12px); font-weight: 500; }
    .alarm-bar span { flex: 1; }
    .empty { padding: 16px; color: var(--secondary-text-color); }
    .intro { color: var(--secondary-text-color); font-size: 14px; line-height: 1.4; margin: 0 0 12px; }
    .row[draggable="true"] { cursor: grab; }
    .row.dragging { opacity: .5; }
    ha-card.drop-target { outline: 2px dashed var(--primary-color); outline-offset: -2px; }
    .level { display: flex; gap: 12px; align-items: flex-start; padding: 12px 16px; border-top: 1px solid var(--divider-color); }
    .level:first-of-type { border-top: 0; }
    .level .chip { flex: none; margin-top: 2px; }
    .level .name { font-weight: 500; }
    .level .effect { color: var(--secondary-text-color); font-size: 13px; margin-top: 2px; }
    .level .body { flex: 1 1 14em; min-width: 0; }
    .level .body ha-form { display: block; margin-top: 8px; }
    .level { flex-wrap: wrap; }
    .form { padding: 0 16px 16px; }
    .card-actions { display: flex; gap: 8px; align-items: center; justify-content: flex-end; padding: 8px 16px 12px; }
    .note { color: var(--success-color, #43a047); font-size: 13px; }
    .guide ol { margin: 0; padding: 0 16px 8px 36px; }
    .guide li { margin: 6px 0; line-height: 1.4; }
    .toolbar { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-bottom: 12px; }
    .toolbar input, .toolbar select { padding: 8px; font: inherit; border-radius: 6px; border: 1px solid var(--divider-color);
      background: var(--card-background-color); color: var(--primary-text-color); }
    .error { color: var(--error-color); padding: 8px 0; }
    .count { font-weight: 600; }
    a { color: var(--primary-color); }
  `}connectedCallback(){super.connectedCallback(),this._start()}disconnectedCallback(){super.disconnectedCallback(),this._unsub?.(),this._unsub=void 0}updated(e){e.has("hass")&&this.hass&&this.hass.language!==this._lang&&(this._lang=this.hass.language,this._t=ie(this._lang),this.requestUpdate())}async _start(){this._lang=this.hass?.language??"en",this._t=ie(this._lang),await Be(),await this._refresh();try{this._unsub=await Ze(this.hass,()=>void this._refresh())}catch(e){this._error=e.message??String(e)}}async _refresh(){try{let[e,t,i]=await Promise.all([De(this.hass),Oe(this.hass),Ce(this.hass)]);this._overview=e,this._messages=t,this._config=i,this._tab==="history"&&(this._history=(await _e(this.hass)).history),this._error=""}catch(e){let t=e;this._error=t.code==="not_ready"?this._t("not_set_up"):t.message??String(e)}}render(){let e=this._t,t=this._overview,i=a=>t?a==="open"?t.open:a==="overview"?t.new:0:0,n=this._tab==="overview"&&t?.new?e("cap_new").replace("{n}",String(t.new)):this._tab==="open"&&t?.open?e("cap_open").replace("{n}",String(t.open)):"";return l`
      <header>
        <div class="bubble">
          <ha-menu-button .hass=${this.hass} .narrow=${this.narrow}></ha-menu-button>
          ${qe(56)}
          <div class="titles"><h1>Message <b>Center</b></h1><div class="tag">${e("tagline")}</div></div>
          ${t?l`<span class="ready ${t.ready?"":"off"}"><span class="led">${A(t.ready?"tick":"alert",12,3.2)}</span>${t.ready?e("ready"):e("not_ready")}</span>`:d}
        </div>
        <svg class="tail" viewBox="-6 0 38 22" preserveAspectRatio="none" aria-hidden="true"><path d="M0 0H26L7 13.2Q3.5 15.6 3.2 11.6z"></path></svg>
      </header>
      <nav>
        ${wt.map(a=>{let p=i(a);return l`<button class=${a===this._tab?"active":""} title=${e(a)} @click=${()=>this._select(a)}>
            <span class="ib">${A(xt[a])}${p?l`<span class="cnt">${p}</span>`:d}</span>
            <span class="lbl">${e(a)}</span>${p?l`<span class="cnt">${p}</span>`:d}
          </button>`})}
      </nav>
      <div class="navcap"><b>${e(this._tab)}</b>${n?l` · ${n}`:d}</div>
      <main>
        ${this._overview?.alarm_active?l`<div class="alarm-bar">
          <span>${e("alarm_active")}${this._overview.alarm_until?l` · ${e("alarm_until")} ${this._time(this._overview.alarm_until)}`:d}</span>
          <ha-button appearance="filled" @click=${this._alarmOff}>${e("alarm_end")}</ha-button>
        </div>`:d}
        ${this._error?l`<div class="error">${this._error}</div>`:d}
        ${this._renderTab()}
      </main>
      ${this._editor?l`<message-center-editor .hass=${this.hass} .t=${e} .heading=${this._editor.heading}
        .fields=${this._editor.fields} .labels=${this._editor.labels} .helpers=${this._editor.helpers} .data=${this._editor.data}
        .onSave=${this._editor.onSave} .onChange=${this._editor.onChange}
        @editor-closed=${()=>{this._editor=void 0,this._scan&&this._tab==="kinds"&&this._runScan()}}></message-center-editor>`:d}
    `}async _select(e){if(this._tab=e,e==="history"&&!this._history)try{this._history=(await _e(this.hass)).history}catch{}e==="settings"&&(this._settings=this._optionsWithDefaults(),this._settingsNote="")}_optionsWithDefaults(){let e=this._config?.options??{};return{history_days:e.history_days??30,sidebar:e.sidebar??!0,hide_titles:e.hide_titles??!1,allow_alarm:e.allow_alarm??!1,lights:e.lights??[],pulse_ms:e.pulse_ms??500,light_spacing:e.light_spacing??0,alarm_lights:e.alarm_lights??[],alarm_interval_ms:e.alarm_interval_ms??1e3,alarm_max_seconds:e.alarm_max_seconds??300,alarm_test_seconds:e.alarm_test_seconds??5,silent_repeat:e.silent_repeat??!1,alarm_channel:e.alarm_channel??"alarm_stream",alarm_tts:e.alarm_tts??!1,button_snooze:e.button_snooze??!0,button_forward:e.button_forward??!0,snooze_minutes:e.snooze_minutes??30,snooze_minutes_2:e.snooze_minutes_2??0,snooze_input:e.snooze_input??!1,lights_always:e.lights_always??[],forward_script:e.forward_script??"",effect_script_1:e.effect_script_1??"",effect_script_2:e.effect_script_2??"",effect_script_3:e.effect_script_3??""}}_nKinds(e){return e===1?this._t("kinds_one"):this._t("kinds_many").replace("{n}",String(e))}_intro(e){return l`<p class="intro">${this._t(e)}</p>`}_renderTab(){switch(this._tab){case"overview":return this._renderOverview();case"open":return this._renderOpen();case"history":return this._renderHistory();case"kinds":return this._renderKinds();case"rules":return this._renderRules();case"recipients":return this._renderRecipients();case"settings":return this._renderSettings()}}_renderOverview(){let e=this._t,t=this._overview;if(!t)return l`<div class="empty">${e("loading")}</div>`;let i=(o,m,c="")=>l`<div class="kpi ${c}"><div class="value">${o}</div><div class="label">${m}</div></div>`,n=t.missing_recipients.length,a=t.disturbed?"bad":t.open||t.new?"warn":"good",p=!t.ready||n||!t.recipients?"bad":"good";return l`
      <div class="groups">
        <section class="kgroup ${a}">
          <h2>${e("group_now")} <span>${e("group_now_sub")}</span></h2>
          <div class="kpis">
            ${i(t.open,e("open"),t.open?"warn":"zero")}
            ${i(t.waiting,e("waiting"),t.waiting?"":"zero")}
            ${i(t.disturbed,e("disturbed"),t.disturbed?"bad":"zero")}
            ${i(t.new,e("new"),t.new?"warn":"zero")}
          </div>
        </section>
        <section class="kgroup ${p}">
          <h2>${e("group_ops")} <span>${e("group_ops_sub")}</span></h2>
          <div class="kpis">
            ${i(t.active_rules,e("active_rules"),t.active_rules?"":"zero")}
            ${i(t.delivered_today,e("delivered_today"),t.delivered_today?"good":"zero")}
            ${i(t.recipients-n+"/"+t.recipients,e("recipients"),n?"bad":"")}
          </div>
        </section>
      </div>
      ${this._config&&!this._config.options.guide_dismissed?l`<ha-card class="guide" .header=${e("guide_title")}>
        <ol>${[1,2,3,4,5].map(o=>l`<li>${e(`guide_${o}`)}</li>`)}</ol>
        <div class="card-actions"><ha-button @click=${()=>this._setGuide(!0)}>${e("guide_dismiss")}</ha-button></div>
      </ha-card>`:d}
      <div class="pair">
        <ha-card .header=${e("new_title")}>
          ${t.unknown.length===0?l`<div class="empty">${e("new_empty")}</div>`:t.unknown.map(o=>this._renderUnknown(o))}
        </ha-card>
        <ha-card .header=${e("last_delivery")}>
          <div class="empty">${t.last_delivery?l`${this._time(t.last_delivery.at)} · ${t.last_delivery.origin==="unknown"?e("unknown_origin"):t.last_delivery.origin} · ${t.last_delivery.title}`:e("none_yet")}</div>
        </ha-card>
      </div>
      <ha-card><message-center-flow .t=${e}></message-center-flow></ha-card>
    `}_renderUnknown(e){let t=this._t;return l`<div class="row">
      <div class="body">
        <div class="title">${e.title}</div>
        <div class="meta">${e.origin_name??(e.origin==="unknown"?t("unknown_origin"):e.origin)}
          ${e.labels.length?l` · ${e.labels.join(", ")}`:d}
          · <span class="count">${e.count}×</span> · ${t("last_seen")} ${this._time(e.last_seen)}</div>
      </div>
      <div class="actions">
        <ha-button appearance="plain" @click=${()=>this._dismiss(e)}>${t("dismiss")}</ha-button>
        <ha-button @click=${()=>this._openKindEditor(void 0,e)}>${t("classify")}</ha-button>
      </div>
    </div>`}async _dismiss(e){try{await Ke(this.hass,e.origin,e.title)}catch(t){this._error=String(t.message??t)}}_renderOpen(){let e=this._t,t=this._messages;return t?l`${this._intro("intro_open")}<ha-card>
      ${t.open.length===0?l`<div class="empty">${e("open_empty")}</div>`:this._renderTable(t.open,!0)}
    </ha-card>`:l`<div class="empty">${e("loading")}</div>`}_renderHistory(){let e=this._t,t=this._config?.groups??[],i=this._config?.kinds??[],n=this._messages?.recent??[],a=this._history??[],p=c=>(!this._filterGroup||(this._filterGroup==="-"?!c.group:c.group===this._filterGroup))&&(!this._filterKind||(this._filterKind==="-"?!c.kind:c.kind===this._filterKind))&&(!this._search||(c.title+" "+c.message+" "+(c.origin_name??"")).toLowerCase().includes(this._search.toLowerCase())),o=n.filter(p),m=a.filter(p);return l`
      ${this._intro("intro_history")}
      <div class="toolbar">
        <select @change=${c=>{this._filterGroup=c.target.value}}>
          <option value="">${e("all_groups")}</option>
          <option value="-">${e("no_group")}</option>
          ${t.map(c=>l`<option value=${c.name}>${c.name}</option>`)}
        </select>
        <select @change=${c=>{this._filterKind=c.target.value}}>
          <option value="">${e("all_kinds")}</option>
          <option value="-">${e("no_kind")}</option>
          ${i.map(c=>l`<option value=${c.name}>${c.name}</option>`)}
        </select>
        <input type="search" placeholder=${e("search")} @input=${c=>{this._search=c.target.value}} />
      </div>
      <ha-card .header=${e("recent")}>
        ${o.length===0?l`<div class="empty">${e("history_empty")}</div>`:this._renderTable(o,!1)}
      </ha-card>
      ${m.length?l`<ha-card .header=${e("older")}>${this._renderTable(m,!1)}</ha-card>`:d}
    `}_renderTable(e,t){let i=this._t;return l`<div class="mtable">
      <div class="thead"><span>${i("level_word")}</span><span>${i("state")}</span><span>${i("message_col")}</span>
        <span>${i("origin")}</span><span class="time">${i("since_col")}</span><span></span></div>
      ${e.map(n=>this._renderMessage(n,t))}
    </div>`}_rowToggled(e,t){if(this._openRows.has(e)===t)return;let i=new Set(this._openRows);t?i.add(e):i.delete(e),this._openRows=i}_renderMessage(e,t){let i=this._t,n=e.state,a=n==="delivered"?"ok":n==="failed"?"fail":n==="discarded"?"drop":"wait",p=$t[n]??"clock",o=e.origin_name??(e.origin==="unknown"?i("unknown_origin"):e.origin),m=this._openRows.has(e.message_id),c=!t&&e.delivered_at?this._time(e.delivered_at):e.reason.toLowerCase()===i(n).toLowerCase()?"":e.reason;return l`<details class="msg s-${a} l${e.priority}" ?open=${m}
      @toggle=${h=>this._rowToggled(e.message_id,h.currentTarget.open)}>
      <summary>
        <span class="lvbox" title=${i(`p${e.priority}`)}>${e.priority}</span>
        <span class="stc" title=${i(n)}>${A(p,18)}<span>${i(n)}</span></span>
        <span class="line"><span class="title">${e.title}</span>${e.count>1?l`<span class="cnt">${e.count}×</span>`:d}<span class="snip">${e.message}</span></span>
        <span class="org">${o}</span>
        <span class="time">${this._time(e.since)}</span>
        <span class="chev">${A("chev",18)}</span>
      </summary>
      ${m?l`<div class="more">
        <div class="more-l">
          <div class="text">${e.message}</div>
          <div class="why">${A(p,15)}<span><b>${i(n)}</b>${c?l` · ${c}`:d}${e.next_try?l` · ${i("next_try")} ${this._time(e.next_try)}`:d}${e.failed_recipients.length?l` · <span class="fail">${i("recipients_failed")}: ${e.failed_recipients.join(", ")}</span>`:d}</span></div>
          ${e.events?.length?l`<div class="events">${e.events.map(h=>l`<div>
            ${this._time(h.at)} · ${i(`ev_${h.kind}`)} ${i(`src_${h.source}`)}${h.detail?l` · ${h.kind==="light_skipped"?i(h.detail==="spacing"?"spacing_skip":h.detail==="effect"?"effect_skip":"nothing_on"):h.detail}`:d}
          </div>`)}</div>`:d}
          ${t||n==="delivered"?l`<div class="actions">
            ${t&&(n==="waiting"||n==="unclear"||n==="retrying")?l`<ha-button appearance="plain" @click=${()=>this._act("send_now",e)}>${i("send_now")}</ha-button>`:d}
            ${t?l`<ha-button appearance="plain" @click=${()=>this._act("discard",e)}>${i("discard")}</ha-button>`:d}
            <ha-button appearance="plain" @click=${()=>this._snooze(e)}>${i("snooze")}</ha-button>
            <ha-button appearance="plain" @click=${()=>this._forward(e)}>${i("forward")}</ha-button>
          </div>`:d}
        </div>
        <dl class="dl">
          <dt>${i("origin")}</dt><dd>${o}</dd>
          <dt>${i("kind")}</dt><dd>${e.kind??"\u2013"}</dd>
          <dt>${i("group")}</dt><dd>${e.group??"\u2013"}</dd>
          <dt>${i("level_word")}</dt><dd>${i(`p${e.priority}`)}</dd>
          <dt>${i("since_col")}</dt><dd>${this._time(e.since)}</dd>
          ${e.count>1?l`<dt>${i("counter")}</dt><dd>${e.count}×</dd>`:d}
          ${e.delivered_at?l`<dt>${i("delivered")}</dt><dd>${this._time(e.delivered_at)}</dd>`:d}
        </dl>
      </div>`:d}
    </details>`}async _act(e,t){try{await te(this.hass,e,t.message_id)}catch(i){this._error=String(i.message??i)}}_snooze(e){let t=this._t;this._editor={heading:`${t("snooze")}: ${e.title}`,fields:[{name:"minutes",required:!0,selector:{number:{min:1,max:10080,mode:"box",unit_of_measurement:"min"}}}],labels:{minutes:t("minutes")},data:{minutes:30},onSave:async i=>{await te(this.hass,"snooze",e.message_id,{minutes:Number(i.minutes)})}}}_forward(e){let t=this._t;this._editor={heading:`${t("forward")}: ${e.title}`,fields:[{name:"note",selector:{text:{multiline:!0}}}],labels:{note:t("note")},data:{note:""},onSave:async i=>{await te(this.hass,"forward",e.message_id,{note:i.note||null})}}}_renderKinds(){let e=this._t,t=this._config;if(!t)return l`<div class="empty">${e("loading")}</div>`;let i=new Set(t.groups.map(a=>a.id)),n=t.kinds.filter(a=>!a.group_id||!i.has(a.group_id));return l`
      ${this._intro("intro_kinds")}
      <div class="toolbar">
        <ha-button @click=${()=>this._openKindEditor()}>${e("add_kind")}</ha-button>
        <ha-button appearance="outlined" @click=${()=>this._openGroupEditor()}>${e("add_group")}</ha-button>
        <ha-button appearance="outlined" .disabled=${this._scanBusy} @click=${this._runScan}>${e("scan_button")}</ha-button>
      </div>
      ${this._renderScan()}
      ${t.groups.map(a=>this._renderGroup(a,t.kinds.filter(p=>p.group_id===a.id)))}
      <ha-card class=${this._dropTarget==="-"?"drop-target":""}
      @dragover=${a=>{this._dragKind&&(a.preventDefault(),a.dataTransfer&&(a.dataTransfer.dropEffect="move"),this._dropTarget="-")}}
      @dragleave=${()=>{this._dropTarget==="-"&&(this._dropTarget="")}}
      @drop=${a=>{a.preventDefault(),this._moveKind(this._dragKind,"-")}}>
        <div class="group-head">
          <ha-icon icon="mdi:folder-outline"></ha-icon>
          <div class="body">
            <div class="title">${e("unassigned")}</div>
            <div class="meta">${this._nKinds(n.length)}</div>
          </div>
          <div class="actions">
            <ha-button appearance="plain" @click=${()=>this._openKindEditor()}>${e("add_kind")}</ha-button>
          </div>
        </div>
        ${n.length===0?l`<div class="empty">${t.kinds.length===0?e("kinds_empty"):e("unassigned_empty")}</div>`:n.map(a=>this._renderKind(a))}
      </ha-card>`}_renderScan(){let e=this._t,t=this._scan;if(!t)return this._scanBusy?l`<ha-card><div class="empty">${e("scan_running")}</div></ha-card>`:d;let i=t.counts.direct,n=t.found.filter(c=>c.status!=="direct").length+t.files.filter(c=>c.status!=="direct").length,a=this._scanAll?t.found:t.found.filter(c=>c.status==="direct"),p=this._scanAll?t.files:t.files.filter(c=>c.status==="direct"),o=new Map;for(let c of a)o.set(c.entity_id,[...o.get(c.entity_id)??[],c]);let m=i===0?e("scan_head_done"):i===1?e("scan_head_one"):e("scan_head_todo").replace("{n}",String(i));return l`<ha-card class="scan">
      <div class="group-head">
        <span class="scan-ico">${A("search",24)}</span>
        <div class="body">
          <div class="title">${e("scan_title")}</div>
          <div class="meta">${e("scan_searched").replace("{a}",String(t.counts.automations)).replace("{s}",String(t.counts.scripts)).replace("{f}",String(t.counts.files))}</div>
        </div>
        <div class="actions">
          <ha-button appearance="plain" .disabled=${this._scanBusy} @click=${this._runScan}>${e("scan_again")}</ha-button>
          <ha-button appearance="plain" @click=${()=>{this._scan=void 0}}>${e("scan_close")}</ha-button>
        </div>
      </div>
      <div class="scan-head ${i?"todo":"done"}">${m}</div>
      ${n?l`<label class="scan-all"><input type="checkbox" .checked=${this._scanAll}
        @change=${c=>{this._scanAll=c.target.checked}} />${e("scan_show_all").replace("{n}",String(n))}</label>`:d}
      ${[...o.values()].map(c=>this._renderScanGroup(c))}
      ${p.length?l`
        <div class="scan-src"><span class="scan-ico">${A("file",18)}</span><b>${e("scan_files_title")}</b></div>
        <div class="scan-note">${e("scan_files_note")}</div>
        ${p.map(c=>l`<div class="row"><div class="body">
          <div class="title"><span class="chip scan-${c.status}">${e(`scan_${c.status}`)}</span><code>${c.file}</code> · ${e("scan_line")} ${c.line}</div>
          <div class="meta"><code>${c.text}</code></div>
        </div></div>`)}`:d}
      <div class="scan-note">${e("scan_limits")}</div>
    </ha-card>`}_renderScanGroup(e){let t=this._t,i=e[0];return l`
      <div class="scan-src">
        <span class="chip">${t(`scan_${i.source}`)}</span><b>${i.name}</b>
        <span class="where">${i.file?l`<code>${i.file}</code>`:t("scan_no_place")}${i.blueprint?l` · ${t("scan_blueprint").replace("{name}",i.blueprint)}`:d}</span>
        ${i.edit_url?l`<a href=${i.edit_url}>${t("scan_open_editor")}</a>`:d}
      </div>
      ${e.map(n=>l`<div class="row">
        <div class="body">
          <div class="title"><span class="chip scan-${n.status}">${t(`scan_${n.status}`)}</span>${n.title??n.first_line??"\u2013"}${n.title?d:l` <span class="chip">${t("scan_no_title")}${n.first_line?l`, ${t("scan_first_line")}`:d}</span>`}</div>
          <div class="meta">${t("scan_target")}: <code>${n.target}</code>${n.line?l` · ${t("scan_line")} ${n.line}`:d}</div>
          ${n.status==="direct"?l`<div class="meta scan-todo">${t("scan_change_target")}${n.title?"":n.suggestion?.mode==="exact"?` ${t("scan_change_title").replace("{title}",n.suggestion.value)}`:` ${t("scan_change_title_free")}`}.</div>`:d}
          ${n.status!=="persistent"&&!n.suggestion?l`<div class="meta">${t(n.title?"scan_title_computed":"scan_title_own")}.</div>`:d}
          ${n.source==="script"&&n.status!=="persistent"&&!n.kind?l`<div class="meta">${t("scan_script_origin")}</div>`:d}
        </div>
        <div class="actions">${n.kind?l`<span class="chip state-delivered">${t("scan_kind")}: ${n.kind}</span>`:n.status==="persistent"?d:l`<ha-button appearance="plain" @click=${()=>this._kindFromScan(n)}>${t("add_kind")}</ha-button>`}</div>
      </div>`)}`}_kindFromScan(e){this._openKindEditor(void 0,{origin:e.origin??"unknown",origin_name:e.origin?e.name:null,labels:[],title:e.suggestion?.value??"",count:0,first_seen:"",last_seen:""},void 0,e.suggestion?.mode??"exact")}_renderGroup(e,t){let i=this._t;return l`<ha-card class=${this._dropTarget===e.id?"drop-target":""}
      @dragover=${n=>{this._dragKind&&(n.preventDefault(),n.dataTransfer&&(n.dataTransfer.dropEffect="move"),this._dropTarget=e.id)}}
      @dragleave=${()=>{this._dropTarget===e.id&&(this._dropTarget="")}}
      @drop=${n=>{n.preventDefault(),this._moveKind(this._dragKind,e.id)}}>
      <div class="group-head">
        <ha-icon .icon=${e.icon||"mdi:folder"}></ha-icon>
        <div class="body">
          <div class="title">${e.name}</div>
          <div class="meta">${this._nKinds(t.length)} · ${i("defaults")}: ${i("priority")} ${e.priority}
            ${e.spacing?l` · ${i("spacing").split(" ")[0]} ${e.spacing} min`:d}
            ${e.expires_after?l` · ${i("expires_after").split(" ")[0]} ${e.expires_after} min`:d}</div>
        </div>
        <div class="actions">
          <ha-button appearance="plain" @click=${()=>this._openKindEditor(void 0,void 0,e.id)}>${i("add_kind")}</ha-button>
          <ha-button appearance="plain" @click=${()=>this._openGroupEditor(e)}>${i("edit")}</ha-button>
          <ha-button appearance="plain" @click=${()=>this._delete(e.id)}>${i("delete")}</ha-button>
        </div>
      </div>
      ${t.length===0?l`<div class="empty">${i("group_empty")}</div>`:t.map(n=>this._renderKind(n))}
    </ha-card>`}_renderKind(e){let t=this._t,i=e.origin?this._config?.origins.find(n=>n.entity_id===e.origin)?.name??e.origin:t("from_any");return l`<div class="row ${this._dragKind===e.id?"dragging":""}" draggable="true"
      @dragstart=${n=>{this._dragKind=e.id,n.dataTransfer?.setData("text/plain",e.id),n.dataTransfer&&(n.dataTransfer.effectAllowed="move")}}
      @dragend=${()=>{this._dragKind="",this._dropTarget=""}}>
      <span class="grip" title=${t("drag_hint")}>${A("grip")}</span>
      <div class="body">
        <div class="title"><span class="chip p${e.priority}">${e.priority}</span>${e.name}${e.active?d:l` <span class="chip">${t("rule_inactive")}</span>`}
          ${e.ties?.length?l` <span class="chip state-waiting" title=${t("tie").replace("{names}",e.ties.join(", "))}>${t("tie").replace("{names}",e.ties.join(", "))}</span>`:d}</div>
        <div class="meta">${i} · ${t(e.title_mode)} ${t("q_open")}${e.title_value}${t("q_close")}
          ${e.no_hold?l` · ${t("no_hold")}`:d}
          ${e.spacing?l` · ${t("spacing").split(" ")[0]} ${e.spacing} min`:d}
          ${e.expires_after?l` · ${t("expires_after").split(" ")[0]} ${e.expires_after} min`:d}</div>
      </div>
      <div class="actions">
        <ha-button appearance="plain" @click=${()=>this._openKindEditor(e)}>${t("edit")}</ha-button>
        <ha-button appearance="plain" @click=${()=>this._delete(e.id)}>${t("delete")}</ha-button>
      </div>
    </div>`}_openKindEditor(e,t,i,n="exact"){let a=this._t,p=this._config,o=[{value:"",label:a("from_any")},...(p?.origins??[]).map(_=>({value:_.entity_id,label:_.name??_.entity_id}))];t&&t.origin!=="unknown"&&!o.some(_=>_.value===t.origin)&&o.push({value:t.origin,label:t.origin_name??t.origin});let m=[{value:"",label:a("no_group")},...(p?.groups??[]).map(_=>({value:_.id,label:_.name}))],c=[{name:"name",required:!0,selector:{text:{}}},{name:"origin",selector:{select:{options:o,mode:"dropdown"}}},{name:"title_mode",required:!0,selector:{select:{options:[{value:"exact",label:a("exact")},{value:"prefix",label:a("prefix")},{value:"contains",label:a("contains")}],mode:"dropdown"}}},{name:"title_value",required:!0,selector:{text:{}}},{name:"group_id",selector:{select:{options:m,mode:"dropdown"}}},{name:"new_group",selector:{text:{}}},{name:"priority",required:!0,selector:{select:{options:[{value:"1",label:a("p1")},{value:"2",label:a("p2")},{value:"3",label:a("p3")}],mode:"dropdown"}}},{name:"no_hold",selector:{boolean:{}}},{name:"spacing",selector:{number:{min:0,max:10080,mode:"box",unit_of_measurement:"min"}}},{name:"expires_after",selector:{number:{min:0,max:10080,mode:"box",unit_of_measurement:"min"}}},{name:"light",selector:{select:{options:[{value:"auto",label:a("light_auto")},{value:"on",label:a("light_on")},{value:"off",label:a("light_off")}],mode:"dropdown"}}},{name:"active",selector:{boolean:{}}}],h=Object.fromEntries(c.map(_=>[_.name,a(_.name)])),$={new_group:a("new_group_helper")},g=(_,T)=>{let H=p?.groups.find(q=>q.id===T);return H?{..._,priority:String(H.priority),spacing:H.spacing,expires_after:H.expires_after}:_},z=e?{...e,origin:e.origin??"",group_id:e.group_id??"",new_group:"",priority:String(e.priority),light:e.light===null?"auto":e.light?"on":"off"}:g({name:t?.title??"",origin:t&&t.origin!=="unknown"?t.origin:"",title_mode:n,title_value:t?.title??"",group_id:i??"",new_group:"",priority:"1",no_hold:!1,spacing:0,expires_after:0,light:"auto",active:!0},i);this._editor={heading:e?`${a("edit")}: ${e.name}`:a("add_kind"),fields:c,labels:h,helpers:$,data:z,onChange:e?void 0:(_,T)=>_.group_id!==T.group_id?g(_,_.group_id):_,onSave:async _=>{if(!String(_.name??"").trim()||!String(_.title_value??"").trim())throw new Error(a("required_missing"));let T=_.group_id||null,H=String(_.new_group??"").trim();if(H){let q=(p?.groups??[]).find(fe=>fe.name.toLowerCase()===H.toLowerCase());q?T=q.id:T=(await K(this.hass,"group",{name:H,icon:null,priority:Number(_.priority),spacing:Number(_.spacing??0),expires_after:Number(_.expires_after??0)})).subentry_id,_.group_id=T,_.new_group=""}await K(this.hass,"kind",{name:_.name,origin:_.origin||null,title_mode:_.title_mode,title_value:_.title_value,group_id:T,priority:Number(_.priority),no_hold:!!_.no_hold,spacing:Number(_.spacing??0),expires_after:Number(_.expires_after??0),light:_.light==="auto"?null:_.light==="on",active:_.active!==!1},e?.id)}}}async _moveKind(e,t){this._dragKind="",this._dropTarget="";let i=this._config?.kinds.find(a=>a.id===e);if(!i)return;let n=t==="-"?null:t;if((i.group_id??null)!==n)try{await K(this.hass,"kind",{name:i.name,origin:i.origin,title_mode:i.title_mode,title_value:i.title_value,group_id:n,priority:i.priority,no_hold:i.no_hold,spacing:i.spacing,expires_after:i.expires_after,light:i.light,active:i.active},i.id),this._error=""}catch(a){this._error=String(a.message??a)}}_openGroupEditor(e){let t=this._t,i=[{name:"name",required:!0,selector:{text:{}}},{name:"icon",selector:{icon:{}}},{name:"priority",selector:{select:{options:[{value:"1",label:t("p1")},{value:"2",label:t("p2")},{value:"3",label:t("p3")}],mode:"dropdown"}}},{name:"spacing",selector:{number:{min:0,max:10080,mode:"box",unit_of_measurement:"min"}}},{name:"expires_after",selector:{number:{min:0,max:10080,mode:"box",unit_of_measurement:"min"}}}],n=Object.fromEntries(i.map(a=>[a.name,t(a.name)]));this._editor={heading:e?`${t("edit")}: ${e.name}`:t("add_group"),fields:i,labels:n,data:e?{...e,icon:e.icon??"",priority:String(e.priority)}:{name:"",icon:"",priority:"1",spacing:0,expires_after:0},onSave:async a=>{await K(this.hass,"group",{name:a.name,icon:a.icon||null,priority:Number(a.priority??1),spacing:Number(a.spacing??0),expires_after:Number(a.expires_after??0)},e?.id)}}}_renderRules(){let e=this._t,t=this._config;if(!t)return l`<div class="empty">${e("loading")}</div>`;let i=n=>e(n==="discard"?"discard_effect":n);return l`
      ${this._intro("intro_rules")}
      <div class="toolbar"><ha-button @click=${()=>this._openRuleEditor()}>${e("add_rule")}</ha-button></div>
      <ha-card>
        ${t.rules.length===0?l`<div class="empty">${e("rules_empty")}</div>`:t.rules.map(n=>l`<div class="row">
          <div class="body">
            <div class="title">
              <span class="chip ${n.active?n.expired?"state-failed":"state-waiting":""}">${n.active?n.expired?e("expired"):e("active"):e("rule_inactive")}</span>
              ${n.name}${n.unknown?l` <span class="chip state-failed">${e("unknown_state")}</span>`:d}
            </div>
            <div class="meta">${n.entity_id} = ${e("q_open")}${n.state}${e("q_close")} (${e("current")}: ${n.current_state??"?"})
              ${n.since?l` · ${e("since")} ${this._time(n.since)} · ${e("until")} ${this._time(n.until)}`:d}
              · ${e("max_hours").split(" ")[0]} ${n.max_hours} h</div>
            <div class="fx">${[n.effect_1,n.effect_2,n.effect_3].map((a,p)=>l`<span class="fx-i l${p+1}"
              title="${e("level_word")} ${p+1}: ${i(a)}"><span class="lvbox">${p+1}</span>${A(kt[a]??"pause",17)}<span>${i(a)}</span></span>`)}</div>
          </div>
          <div class="actions">
            <ha-button appearance="plain" @click=${()=>this._openRuleEditor(n)}>${e("edit")}</ha-button>
            <ha-button appearance="plain" @click=${()=>this._delete(n.id)}>${e("delete")}</ha-button>
          </div>
        </div>`)}
      </ha-card>`}_openRuleEditor(e){let t=this._t,i={select:{options:[{value:"pass",label:t("pass")},{value:"hold",label:t("hold")},{value:"discard",label:t("discard_effect")}],mode:"dropdown"}},n=(o,m)=>{let c=this._knownStates(String(o??""));return m&&!c.includes(String(m))&&c.unshift(String(m)),[{name:"name",required:!0,selector:{text:{}}},{name:"entity_id",required:!0,selector:{entity:{}}},{name:"state",required:!0,selector:{select:{options:c.map(h=>({value:h,label:h})),mode:"dropdown",custom_value:!0}}},{name:"effect_1",selector:i},{name:"effect_2",selector:i},{name:"effect_3",selector:i},{name:"max_hours",selector:{number:{min:1,max:168,mode:"box",unit_of_measurement:"h"}}}]},a={name:t("name"),entity_id:t("entity"),state:t("rule_state"),effect_1:t("effect_1"),effect_2:t("effect_2"),effect_3:t("effect_3"),max_hours:t("max_hours")},p=e?{...e}:{name:"",entity_id:"",state:"on",effect_1:"hold",effect_2:"hold",effect_3:"pass",max_hours:12};this._editor={heading:e?`${t("edit")}: ${e.name}`:t("add_rule"),fields:n(p.entity_id,p.state),labels:a,helpers:{state:t("rule_state_helper")},data:p,onChange:(o,m)=>{if(o.entity_id!==m.entity_id&&this._editor){let c=this._knownStates(String(o.entity_id??"")),h=c.includes(String(o.state))?o.state:c[0]??o.state;o={...o,state:h},this._editor={...this._editor,fields:n(o.entity_id,h)}}return o},onSave:async o=>{await K(this.hass,"rule",{name:o.name,entity_id:o.entity_id,state:o.state,effect_1:o.effect_1??"hold",effect_2:o.effect_2??"hold",effect_3:o.effect_3??"pass",max_hours:Number(o.max_hours??12)},e?.id)}}}_knownStates(e){let t=this.hass?.states?.[e],i=e.split(".")[0],n={input_boolean:["on","off"],switch:["on","off"],binary_sensor:["on","off"],light:["on","off"],person:["home","not_home"],device_tracker:["home","not_home"],sun:["above_horizon","below_horizon"],alarm_control_panel:["disarmed","armed_home","armed_away","armed_night","armed_vacation","triggered"],lock:["locked","unlocked"],cover:["open","closed"],calendar:["on","off"],schedule:["on","off"],media_player:["playing","paused","idle","off"],vacuum:["cleaning","docked","returning","idle"]},a=t?.attributes?.options??[],p=[...t?[t.state]:[],...a,...n[i]??[]];return[...new Set(p.filter(o=>o&&o!=="unknown"&&o!=="unavailable"))]}_renderRecipients(){let e=this._t,t=this._config;if(!t)return l`<div class="empty">${e("loading")}</div>`;let i=t.recipients.map(o=>({name:o.action,selector:{boolean:{}}})),n=Object.fromEntries(t.recipients.map(o=>[o.action,o.name])),a=Object.fromEntries(t.recipients.map(o=>[o.action,`${o.platform} \xB7 notify.${o.action} \xB7 ${o.available?e("available"):e("unavailable")} \xB7 ${o.last_error?`${e("last_error")}: ${o.last_error.error} (${this._time(o.last_error.at)})`:e("no_error")}`])),p=Object.fromEntries(t.recipients.map(o=>[o.action,o.configured]));return l`<ha-card>
      <div class="empty">${e("recipients_intro")}</div>
      <div class="form">
        <ha-form .hass=${this.hass} .schema=${i} .data=${p}
          .computeLabel=${o=>n[o.name]??o.name} .computeHelper=${o=>a[o.name]}
          @value-changed=${o=>this._recipientsChanged(o.detail.value)}></ha-form>
      </div>
      <div class="empty">${e("recipients_hint")} <a href="/config/integrations/integration/message_center">→</a></div>
    </ha-card>`}async _recipientsChanged(e){let t=Object.entries(e).filter(([,i])=>i).map(([i])=>i);try{await Ue(this.hass,t),this._error=""}catch(i){let n=i;this._error=n.code==="at_least_one"?this._t("at_least_one"):String(n.message??i),await this._refresh()}}_renderSettings(){let e=this._t;if(!this._config)return l`<div class="empty">${e("loading")}</div>`;let t=this._settings??(this._settings=this._optionsWithDefaults()),i=g=>{this._settings={...t,...g.detail.value},this._settingsNote=""},n=[{name:"lights",selector:{entity:{domain:["light","switch"],multiple:!0}}},{name:"pulse_ms",required:!0,selector:{number:{min:100,max:1e4,step:50,mode:"box",unit_of_measurement:"ms"}}},{name:"light_spacing",required:!0,selector:{number:{min:0,max:600,mode:"box",unit_of_measurement:"s"}}},{name:"lights_always",selector:{entity:{domain:["light","switch"],multiple:!0}}}],a=[{name:"alarm_lights",selector:{entity:{domain:["light","switch"],multiple:!0}}},{name:"alarm_interval_ms",required:!0,selector:{number:{min:100,max:5e3,step:50,mode:"box",unit_of_measurement:"ms"}}},{name:"alarm_max_seconds",required:!0,selector:{number:{min:5,max:3600,mode:"box",unit_of_measurement:"s"}}},{name:"alarm_test_seconds",required:!0,selector:{number:{min:1,max:60,mode:"box",unit_of_measurement:"s"}}},{name:"alarm_channel",required:!0,selector:{select:{mode:"dropdown",options:[{value:"alarm_stream",label:e("alarm_channel_stream")},{value:"alarm_stream_max",label:e("alarm_channel_max")},{value:"message_center_alarm",label:e("alarm_channel_own")}]}}},{name:"alarm_tts",selector:{boolean:{}}}],p={alarm_lights:e("alarm_lights_helper"),alarm_channel:e("alarm_channel_helper")},o=[{name:"button_snooze",selector:{boolean:{}}},{name:"snooze_minutes",required:!0,selector:{number:{min:1,max:10080,mode:"box",unit_of_measurement:"min"}}},{name:"snooze_minutes_2",selector:{number:{min:0,max:10080,mode:"box",unit_of_measurement:"min"}}},{name:"snooze_input",selector:{boolean:{}}},{name:"button_forward",selector:{boolean:{}}},{name:"forward_script",selector:{entity:{domain:"script"}}}],m=[{name:"history_days",required:!0,selector:{number:{min:1,max:365,mode:"box",unit_of_measurement:"d"}}},{name:"sidebar",selector:{boolean:{}}},{name:"hide_titles",selector:{boolean:{}}},{name:"allow_alarm",selector:{boolean:{}}},{name:"silent_repeat",selector:{boolean:{}}}],c=g=>[{name:`effect_script_${g}`,selector:{entity:{domain:"script"}}}],h=g=>l`<div class="level">
      <span class="chip p${g}">${g}</span>
      <div class="body"><div class="name">${e(`level_${g}_name`)}</div><div class="effect">${e(`level_${g}_effect`)}</div>
        <ha-form .hass=${this.hass} .schema=${c(g)} .data=${t}
          .computeLabel=${z=>e(z.name)} .computeHelper=${()=>e("effect_script_helper")} @value-changed=${i}></ha-form>
      </div>
      <div class="actions"><ha-button appearance="outlined" @click=${()=>this._sendTest(g)}>${e("test")}</ha-button></div>
    </div>`,$={lights:e("lights_helper"),light_spacing:e("light_spacing_helper"),lights_always:e("lights_always_helper")};return l`
      ${this._intro("intro_settings")}
      <ha-card .header=${e("levels_title")}>
        <div class="empty">${e("test_hint")}${this._testNote?l` <span class="note">${this._testNote}</span>`:d}</div>
        ${h(1)}${h(2)}
        <div class="form">
          <ha-form .hass=${this.hass} .schema=${n} .data=${t}
            .computeLabel=${g=>e(g.name)} .computeHelper=${g=>$[g.name]}
            @value-changed=${i}></ha-form>
        </div>
        ${h(3)}
        <div class="form">
          <ha-form .hass=${this.hass} .schema=${a} .data=${t}
            .computeLabel=${g=>e(g.name)} .computeHelper=${g=>p[g.name]} @value-changed=${i}></ha-form>
        </div>
      </ha-card>
      <ha-card .header=${e("buttons_title")}>
        <div class="empty">${e("buttons_intro")}</div>
        <div class="form">
          <ha-form .hass=${this.hass} .schema=${o} .data=${t}
            .computeLabel=${g=>e(g.name)} .computeHelper=${g=>g.name==="snooze_input"?e("snooze_input_helper"):g.name==="forward_script"?e("forward_script_helper"):void 0}
            @value-changed=${i}></ha-form>
        </div>
      </ha-card>
      <ha-card .header=${e("options_title")}>
        <div class="form">
          <ha-form .hass=${this.hass} .schema=${m} .data=${t}
            .computeLabel=${g=>e(g.name)} @value-changed=${i}></ha-form>
        </div>
        <div class="card-actions">
          ${this._settingsNote?l`<span class="note">${this._settingsNote}</span>`:d}
          <ha-button appearance="plain" @click=${()=>this._setGuide(!1)}>${e("guide_show")}</ha-button>
          <ha-button @click=${this._saveSettings}>${e("save")}</ha-button>
        </div>
      </ha-card>`}async _setGuide(e){try{await ge(this.hass,{guide_dismissed:e}),e||(this._tab="overview")}catch(t){this._error=String(t.message??t)}}async _sendTest(e){let t=this._t;if(!(e===3&&!window.confirm(t("confirm_alarm_test")))){this._testNote="";try{let i=await Ie(this.hass,e),n=[t("test_sent").replace("{n}",String(e)).replace("{names}",i.sent.join(", ")||"\u2013")];e===2&&n.push(i.lights.length?t("test_lights").replace("{lights}",i.lights.join(", ")):t("test_no_lights")),e===3&&i.lights.length&&n.push(t("test_alarm").replace("{lights}",i.lights.join(", "))),i.script&&n.push(i.script_error?t("test_script_failed").replace("{script}",i.script).replace("{error}",i.script_error):t("test_script").replace("{script}",i.script)),i.failed.length&&n.push(t("test_failed").replace("{names}",i.failed.join(", "))),this._testNote=n.join(" \xB7 "),this._error=""}catch(i){this._error=String(i.message??i)}}}async _delete(e){if(window.confirm(this._t("confirm_delete")))try{await Pe(this.hass,e)}catch(t){this._error=String(t.message??t)}}_time(e){if(!e)return"?";let t=new Date(e),i=this.hass?.language??"en",n=new Date;return t.toDateString()===n.toDateString()?t.toLocaleTimeString(i,{hour:"2-digit",minute:"2-digit"}):t.toLocaleString(i,{day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"})}};u([y({attribute:!1})],b.prototype,"hass",2),u([y({type:Boolean})],b.prototype,"narrow",2),u([v()],b.prototype,"_tab",2),u([v()],b.prototype,"_overview",2),u([v()],b.prototype,"_messages",2),u([v()],b.prototype,"_history",2),u([v()],b.prototype,"_config",2),u([v()],b.prototype,"_error",2),u([v()],b.prototype,"_editor",2),u([v()],b.prototype,"_filterGroup",2),u([v()],b.prototype,"_filterKind",2),u([v()],b.prototype,"_search",2),u([v()],b.prototype,"_settings",2),u([v()],b.prototype,"_settingsNote",2),u([v()],b.prototype,"_testNote",2),u([v()],b.prototype,"_dragKind",2),u([v()],b.prototype,"_dropTarget",2),u([v()],b.prototype,"_openRows",2),u([v()],b.prototype,"_scan",2),u([v()],b.prototype,"_scanBusy",2),u([v()],b.prototype,"_scanAll",2);customElements.get("message-center-panel")||customElements.define("message-center-panel",b);export{b as MessageCenterPanel};
