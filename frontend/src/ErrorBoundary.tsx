import {Component,type ErrorInfo,type ReactNode} from 'react';

export class ErrorBoundary extends Component<{children:ReactNode},{failed:boolean}>{
  state={failed:false};
  static getDerivedStateFromError(){return {failed:true}}
  componentDidCatch(_error:Error,_info:ErrorInfo){/* No identity or record data is logged. */}
  render(){return this.state.failed?<main className="access-gate"><section className="access-card" role="alert"><h1>This page could not be displayed</h1><p>Your saved records remain on the server. Reload the workspace to try again.</p><button className="primary" onClick={()=>window.location.reload()}>Reload workspace</button><p>If the problem continues, contact your division administrator with the page address.</p></section></main>:this.props.children}
}
