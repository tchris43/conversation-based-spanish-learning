type MountainGraphicProps = {
  faded?: boolean;
};

export function MountainGraphic({ faded = false }: MountainGraphicProps) {
  return (
    <svg
      viewBox="0 0 1200 760"
      width="100%"
      height="100%"
      aria-hidden="true"
      style={{ opacity: faded ? 0.08 : 1 }}
    >
      <defs>
        <linearGradient id="peakLight" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#857d77" />
          <stop offset="100%" stopColor="#67605b" />
        </linearGradient>
        <linearGradient id="peakDark" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#5b5550" />
          <stop offset="100%" stopColor="#3f3a36" />
        </linearGradient>
      </defs>

      <path d="M180 640 L520 210 L720 470 L900 280 L1070 640 Z" fill="url(#peakDark)" />
      <path d="M180 640 L520 210 L610 640 Z" fill="url(#peakLight)" />
      <path d="M520 210 L590 318 L555 318 Z" fill="#f7f3ec" opacity="0.92" />
      <path d="M520 210 L590 318 L645 640 Z" fill="#4f4944" opacity="0.22" />
      <path
        d="M190 640
           C 250 600, 300 560, 360 548
           C 430 532, 470 498, 516 448
           C 555 406, 606 388, 675 390
           C 758 392, 812 354, 874 306"
        fill="none"
        stroke="#efe6d7"
        strokeWidth="8"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.95"
      />
    </svg>
  );
}
