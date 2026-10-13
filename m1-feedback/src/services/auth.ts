export interface Identity {
  subject: string;
  displayName: string;
  authMode: 'demo';
}

export function enterDemo(): Identity {
  return {
    subject: 'demo:tester',
    displayName: 'M1 内部测试员',
    authMode: 'demo',
  };
}
