import type {ReactNode} from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import {X} from 'lucide-react';
export {Corridor} from './Corridor';
export {Timeline} from './Timeline';

export function Panel({title,aside,children,className=''}:{title:string;aside?:ReactNode;children:ReactNode;className?:string}) {
  return <section className={'panel '+className}><div className="panel-head"><h2>{title}</h2>{aside}</div>{children}</section>;
}
export function Badge({children,tone='neutral'}:{children:ReactNode;tone?:string}) {
  return <span className={'badge '+tone}>{children}</span>;
}
export function Sheet({open,onClose,title,children,wide=false}:{open:boolean;onClose:()=>void;title:string;children:ReactNode;wide?:boolean}) {
  return <Dialog.Root open={open} onOpenChange={value=>!value&&onClose()}><Dialog.Portal><Dialog.Overlay className="overlay"/><Dialog.Content className={'sheet '+(wide?'wide':'')} aria-describedby={undefined}><div className="sheet-topline"/><div className="panel-head"><div><span className="section-overline">WORKSPACE INSPECTOR</span><Dialog.Title>{title}</Dialog.Title></div><Dialog.Close className="icon-button" aria-label="Close details"><X size={20}/></Dialog.Close></div><div className="sheet-body">{children}</div></Dialog.Content></Dialog.Portal></Dialog.Root>;
}
