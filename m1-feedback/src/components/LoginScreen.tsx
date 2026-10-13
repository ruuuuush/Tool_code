import type { RefObject } from 'react';
import PitchScene from './PitchScene';

interface LoginScreenProps {
  headingRef: RefObject<HTMLHeadingElement | null>;
  onEnter: () => void;
}

export default function LoginScreen({ headingRef, onEnter }: LoginScreenProps) {
  return (
    <div className="login-shell">
      <a className="skip-link" href="#login-content">跳到登录入口</a>
      <header className="site-header login-header">
        <div className="brand-lockup" aria-label="M1 问题反馈站">
          <span className="brand-mark">M1<span className="brand-dot" /></span>
          <span className="brand-copy">VAR ROOM<span>问题反馈站</span></span>
        </div>
        <span className="header-label">INTERNAL PLAYTEST / 内部测试</span>
      </header>

      <main className="login-layout" id="login-content">
        <section className="login-hero">
          <div className="eyebrow"><span className="line-marker" />M1 FIELD REPORT</div>
          <h1 ref={headingRef} tabIndex={-1} className="login-title">
            回放问题。<br />让<span>好球</span>继续。
          </h1>
          <p className="hero-description">每个细节，都影响下一场比赛。<br />把异常留在回放里，把更好的体验带回球场。</p>
          <div className="hero-tags"><span>发现</span><i /><span>还原</span><i /><span>改进</span></div>
          <PitchScene />
          <span className="hero-watermark" aria-hidden="true">M1</span>
        </section>

        <section className="login-card" aria-labelledby="login-card-title">
          <div className="card-topline"><span>PLAYER ACCESS</span><span className="demo-badge"><span className="status-dot" />演示模式</span></div>
          <div className="access-number" aria-hidden="true">01<span>/ ENTRY</span></div>
          <h2 id="login-card-title">欢迎来到回放室</h2>
          <p className="card-description">为 M1 内部测试与研发准备的问题反馈入口。</p>
          <div className="identity-placeholder">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M8 10V7a4 4 0 0 1 8 0v3M6 10h12v10H6V10Z" stroke="currentColor" strokeWidth="1.5" /><circle cx="12" cy="15" r="1" fill="currentColor" /></svg>
            <div><strong>OpenID 登录</strong><span>OpenID 待接入 · 演示模式</span></div>
            <span className="small-label">待接入</span>
          </div>
          <button className="button-primary login-enter" type="button" onClick={onEnter}>
            使用演示身份进入<span aria-hidden="true">↗</span>
          </button>
          <p className="demo-explanation">以「M1 内部测试员」体验完整反馈流程。<br />不采集密码，不验证真实身份。</p>
          <div className="login-card-divider" />
          <ol className="access-features">
            <li><span>01</span><div><strong>定位比赛中的异常</strong><p>分类、版本、复现信息，一处整理。</p></div></li>
            <li><span>02</span><div><strong>用回放保留现场</strong><p>图片与视频，仅在本机选择和预览。</p></div></li>
            <li><span>03</span><div><strong>准备好一张问题单</strong><p>生成通用 JSON，真实开单后续接入。</p></div></li>
          </ol>
          <div className="local-notice"><span aria-hidden="true">⌁</span>本地演示，不上传附件，不提交易协作。</div>
        </section>
      </main>

      <footer className="site-footer login-footer">
        <span>M1 / EVERY DETAIL CHANGES THE GAME</span>
        <span>本地演示 · 刷新页面会清空本地内容</span>
      </footer>
    </div>
  );
}
