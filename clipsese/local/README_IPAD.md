# ClipSese desde iPad (sin Railway, con la PC como motor)

**El iPad no instala Python/FFmpeg ni renderiza clips directamente.** Abre ClipSese desde Safari mientras la computadora Windows procesa los archivos. La PC debe estar encendida, ClipSese LOCAL debe estar abierto y ambos dispositivos deben entrar a tu red privada Tailscale.

Esta solución permite usar ClipSese desde el iPad tanto en casa como fuera de ella, siempre que tu PC permanezca encendida, con internet y con ClipSese abierto. No necesitas pagar un servidor de videos. Revisa las condiciones vigentes de Tailscale para el uso que darás a la app; su plan Personal está destinado a uso personal no comercial.

## Configuración inicial (una sola vez)

1. **Primero termina de instalar y probar ClipSese LOCAL en Windows** con `INSTALAR_LOCAL.bat` y `INICIAR_LOCAL.bat`. Comprueba que funciona `http://127.0.0.1:8000/` en el navegador de TU PC.
2. **Instala Tailscale en Windows desde su página oficial**: https://tailscale.com/download/windows. Abre la aplicación e inicia sesión con tu cuenta.
3. **Instala Tailscale en el iPad desde su página oficial**: https://tailscale.com/download/ios (te lleva a App Store). Inicia sesión con la misma cuenta y autoriza la VPN solicitada por iPadOS. Deja la conexión de Tailscale activada.
4. **En la PC, deja abierto INICIAR_LOCAL.bat** y haz doble clic en `CONFIGURAR_IPAD.bat`. Este archivo ejecuta exclusivamente **Tailscale Serve**: comparte tu ClipSese solamente con los dispositivos autorizados de tu red Tailscale; NO utiliza Funnel y NO publica la aplicación a internet abierto.
5. Si Tailscale te pide habilitar certificados HTTPS, entra a los ajustes de DNS de tu red Tailscale y activa HTTPS. Después vuelve a ejecutar `CONFIGURAR_IPAD.bat`.
6. La ventana mostrará una dirección privada HTTPS de tu computadora, normalmente de la forma `https://nombre-de-tu-pc.nombre-de-tu-red.ts.net`. Copia ESA dirección y ábrela en **Safari del iPad** con Tailscale conectado. No abras `localhost` ni `127.0.0.1` en el iPad: esas direcciones apuntan al propio iPad, no a la PC.
7. Opcional: en Safari toca **Compartir > Añadir a pantalla de inicio > Abrir como app > Añadir**. Tendrás un icono ClipSese como si fuera una aplicación instalada. El icono es solo acceso directo a la web privada; para generar clips debe seguir encendida la PC.

En uso diario basta con abrir `INICIAR_LOCAL.bat` en la PC, activar Tailscale en el iPad y abrir ese icono de Safari. `CONFIGURAR_IPAD.bat` configura Serve en segundo plano; normalmente no se repite salvo cambios de Tailscale.

## Funcionalidad y límites

- Desde el iPad se pueden ajustar tiempos, buscar jugadores o temas, elegir los tres layouts y descargar MP4 usando **Descargar último MP4**. La descarga se transmite como archivo directo a Safari, sin cargar el MP4 completo en JavaScript; usa el gestor de descargas de Safari para guardarlo en **Archivos**.
- El trabajo pesado se realiza EN LA PC, usando sus discos, CPU y, si funciona en ese sistema, NVENC de NVIDIA. Los videos se transmiten al iPad mientras editas, así que una conexión lenta, especialmente el internet de subida de tu casa, puede afectar el preview.
- La vista vertical usa Safari y canvas. Ya hay compatibilidad móvil en el código, pero el comportamiento en TU iPad específico se debe probar con un clip corto. Si Safari no refresca la vista, recarga y verifica el preview antes de exportar.
- `Finalizar y limpiar` elimina los temporales DEL MOTOR EN LA PC. Primero confirma que el clip esté completamente descargado y accesible en la app Archivos del iPad. Ese botón no borra lo guardado en Archivos.
- La aplicación está disponible solamente para dispositivos autenticados y autorizados en tu red privada. Usa una cuenta personal con acceso limitado, habilita autenticación multifactor y no compartas la dirección con desconocidos. No abras el puerto 8000 en el router, no uses Tailscale Funnel y no subas cookies a GitHub.
- Si quieres utilizar ClipSese con la PC apagada y sin servidor externo, necesitaríamos desarrollar un motor de render distinto que corra EN el iPad; no es esta versión y probablemente tendría límites importantes para videos 1440p60 y 90 segundos.

Documentación oficial: https://tailscale.com/docs/features/tailscale-serve y https://support.apple.com/guide/ipad/open-as-web-app-ipad8f1f7a29/ipados.
