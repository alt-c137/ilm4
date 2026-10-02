/** WebRTC для звонков. В Expo Go его нет — модуль есть только в собранном приложении (EAS build).
 *  Поэтому подключаем осторожно: нет модуля — звонки в приложении просто недоступны. */
let mod: any = null;
try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  mod = require('react-native-webrtc');
  if (!mod?.RTCPeerConnection || !mod?.mediaDevices) mod = null;
} catch {
  mod = null;
}

export const webrtc = mod as null | {
  RTCPeerConnection: any; RTCIceCandidate: any; RTCSessionDescription: any; mediaDevices: any; RTCView: any;
};
export const callsSupported = !!mod;
