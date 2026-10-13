export default function PitchScene({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`pitch-scene${compact ? ' pitch-compact' : ''}`} aria-hidden="true">
      <div className="pitch-glow" />
      <svg viewBox="0 0 720 430" fill="none" className="pitch-svg">
        <defs>
          <linearGradient id={compact ? 'pitch-fill-small' : 'pitch-fill'} x1="360" y1="20" x2="360" y2="420" gradientUnits="userSpaceOnUse">
            <stop stopColor="#242428" stopOpacity=".2" />
            <stop offset="1" stopColor="#3a242b" stopOpacity=".7" />
          </linearGradient>
        </defs>
        <path d="M154 48H566L688 388H32L154 48Z" fill={`url(#${compact ? 'pitch-fill-small' : 'pitch-fill'})`} />
        <g stroke="#d4d4da" strokeOpacity=".27" strokeWidth="1.5">
          <path d="M154 48H566L688 388H32L154 48Z" />
          <path d="M96 210H624M360 48V388" />
          <ellipse cx="360" cy="210" rx="70" ry="47" />
          <path d="M256 48L240 112H480L464 48M303 48L298 76H422L417 48" />
          <path d="M194 388L221 299H499L526 388M278 388L289 347H431L442 388" />
          <path d="M314 112C324 132 396 132 406 112M296 299C317 278 403 278 424 299" />
          <path d="M325 48V32H395V48M313 388V409H407V388" />
        </g>
        <g stroke="#77777f" strokeOpacity=".12" strokeWidth="24">
          <path d="M149 71H573M132 118H589M113 169H609M91 227H630M65 299H655M43 360H677" />
        </g>
        <g fill="#b0b0b7" opacity=".5">
          <circle cx="260" cy="176" r="4" /><circle cx="464" cy="161" r="4" />
          <circle cx="209" cy="279" r="4" /><circle cx="402" cy="305" r="4" />
          <circle cx="360" cy="65" r="4" /><circle cx="360" cy="367" r="4" />
        </g>
        <path d="M487 266C451 251 390 279 354 241S283 181 339 119" stroke="#ff4054" strokeWidth="2" strokeDasharray="5 8" />
        <path d="M328 126L339 119L342 133" stroke="#ff4054" strokeWidth="2" />
        <circle cx="487" cy="266" r="8" fill="#ff4054" />
        <circle cx="487" cy="266" r="20" stroke="#ff4054" strokeOpacity=".32" />
        <rect x="464" y="243" width="46" height="46" rx="3" stroke="#ff4054" strokeOpacity=".75" strokeDasharray="8 8" />
        <g fill="#ff4054" fontSize="9" fontFamily="monospace" letterSpacing="2">
          <text x="521" y="258">REPLAY</text>
          <text x="521" y="275" fill="#a3a3aa">M1 / VAR</text>
        </g>
      </svg>
      {!compact && <span className="pitch-caption">THE FIELD IS OUR STARTING POINT.</span>}
    </div>
  );
}
