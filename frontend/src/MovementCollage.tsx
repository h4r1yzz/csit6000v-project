const photos = [
  ['gym','A rack of dumbbells in a gym','Make space'],
  ['stretch','People exercising on mats in a studio','Find balance'],
  ['strength','An athlete preparing to lift a barbell','Build strength'],
  ['training','A person performing a floor exercise','Show up'],
  ['running','A runner climbing outdoor steps','Keep moving'],
  ['yoga','A silhouette stretching beside the sea','Take a breath'],
]
export default function MovementCollage() {
  return <section className="movement-collage" aria-labelledby="movement-title">
    <div className="movement-heading"><div><span>THERE’S NO ONE WAY TO MOVE</span><h2 id="movement-title">Find your <em>kind of strong.</em></h2></div></div>
    <div className="movement-photos">{photos.map(([file,alt,caption],i)=><figure key={file} className={`movement-photo photo-${i}`}><img src={`/images/movement/${file}.jpg`} alt={alt} width="640" height="800" loading="lazy" decoding="async"/><figcaption><span>0{i+1}</span>{caption}</figcaption></figure>)}</div>
    <div className="movement-caption"><span>Small steps. Different rhythms. All yours.</span><small>Movement inspiration · Current tracking: curls, squats &amp; arm circles</small></div>
  </section>
}
