<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EmpowerBands — Shirt Giveaway</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@600;700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root{
    --eb-navy:#12233F;
    --eb-blue:#2D6CDF;
    --eb-blue-dark:#1F4FB0;
    --eb-blue-tint:#EAF1FF;
    --eb-coral:#FF6B57;
    --eb-cream:#F7F5F0;
    --eb-white:#FFFFFF;
    --eb-ink:#12233F;
    --eb-muted:#5B6B85;
    --eb-line:#DCE3F0;
    --eb-radius:16px;
  }
  .eb-giveaway *{box-sizing:border-box;}
  .eb-giveaway{
    font-family:'Inter',system-ui,sans-serif;
    color:var(--eb-ink);
    background:var(--eb-cream);
    padding:64px 20px;
  }
  .eb-giveaway h2, .eb-giveaway h3{font-family:'Poppins',sans-serif;margin:0;}
  .eb-wrap{max-width:1080px;margin:0 auto;}

  .eb-head{text-align:center;max-width:640px;margin:0 auto 44px;}
  .eb-eyebrow{
    display:inline-flex;align-items:center;gap:8px;
    background:var(--eb-blue-tint);color:var(--eb-blue-dark);
    font-family:'Poppins',sans-serif;font-weight:700;font-size:13px;
    letter-spacing:.04em;text-transform:uppercase;
    padding:8px 16px;border-radius:999px;margin-bottom:18px;
  }
  .eb-head h2{font-size:clamp(28px,4vw,40px);font-weight:800;line-height:1.15;color:var(--eb-navy);}
  .eb-head h2 span{color:var(--eb-blue);}
  .eb-head p{font-size:16px;line-height:1.65;color:var(--eb-muted);margin-top:14px;}

  .eb-grid{
    display:grid;grid-template-columns:0.85fr 1fr;gap:28px;align-items:stretch;
  }
  @media (max-width:800px){ .eb-grid{grid-template-columns:1fr;} }

  .eb-card{
    background:var(--eb-white);border:1px solid var(--eb-line);
    border-radius:var(--eb-radius);padding:32px;
  }

  /* shirt visual card */
  .eb-shirt-card{display:flex;flex-direction:column;align-items:center;text-align:center;justify-content:center;position:relative;overflow:hidden;}
  .eb-shirt-badge{
    position:absolute;top:18px;right:-38px;
    background:var(--eb-coral);color:#fff;font-family:'Poppins',sans-serif;
    font-weight:700;font-size:12px;letter-spacing:.03em;text-transform:uppercase;
    padding:6px 44px;transform:rotate(38deg);
  }
  .eb-shirt-svg{width:180px;height:180px;margin:8px 0 18px;}
  .eb-shirt-card h3{font-size:20px;color:var(--eb-navy);margin-bottom:6px;}
  .eb-shirt-card p{font-size:14px;color:var(--eb-muted);line-height:1.6;margin:0 0 18px;}
  .eb-price-row{
    display:flex;align-items:baseline;gap:8px;justify-content:center;margin-bottom:18px;
  }
  .eb-price{font-family:'Poppins',sans-serif;font-weight:800;font-size:26px;color:var(--eb-navy);}
  .eb-price-note{font-size:13px;color:var(--eb-muted);}
  .eb-buy-link{
    font-family:'Poppins',sans-serif;font-weight:600;font-size:14px;
    color:var(--eb-blue-dark);text-decoration:none;border-bottom:1px solid var(--eb-blue-dark);
    padding-bottom:2px;
  }
  .eb-buy-link:hover{color:var(--eb-blue);border-color:var(--eb-blue);}

  /* entry card */
  .eb-entry-card{display:flex;flex-direction:column;}
  .eb-entry-card h3{font-size:20px;color:var(--eb-navy);margin-bottom:18px;}

  .eb-steps{list-style:none;margin:0 0 26px;padding:0;display:flex;flex-direction:column;gap:14px;}
  .eb-steps li{display:flex;gap:12px;align-items:flex-start;}
  .eb-step-num{
    flex:0 0 auto;width:28px;height:28px;border-radius:50%;
    background:var(--eb-blue-tint);color:var(--eb-blue-dark);
    font-family:'Poppins',sans-serif;font-weight:700;font-size:13px;
    display:flex;align-items:center;justify-content:center;
  }
  .eb-steps p{margin:0;font-size:14.5px;line-height:1.55;color:var(--eb-ink);padding-top:3px;}
  .eb-steps a{color:var(--eb-blue-dark);font-weight:600;}

  .eb-form{display:flex;flex-direction:column;gap:14px;border-top:1px solid var(--eb-line);padding-top:22px;}
  .eb-field{display:flex;flex-direction:column;gap:6px;}
  .eb-field label{font-size:13px;font-weight:600;color:var(--eb-navy);}
  .eb-field input{
    font-family:'Inter',sans-serif;font-size:15px;
    padding:11px 13px;border:1px solid var(--eb-line);border-radius:10px;
    background:var(--eb-cream);color:var(--eb-ink);outline:none;
  }
  .eb-field input:focus{border-color:var(--eb-blue);box-shadow:0 0 0 3px var(--eb-blue-tint);}

  .eb-submit{
    margin-top:4px;font-family:'Poppins',sans-serif;font-weight:700;font-size:15px;
    background:var(--eb-blue);color:#fff;border:none;border-radius:10px;
    padding:13px 20px;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:8px;
  }
  .eb-submit:hover{background:var(--eb-blue-dark);}
  .eb-submit:focus-visible{outline:3px solid var(--eb-coral);outline-offset:2px;}

  .eb-form-note{font-size:12.5px;color:var(--eb-muted);text-align:center;margin-top:2px;}

  .eb-success{
    display:none;border-top:1px solid var(--eb-line);padding-top:22px;
    text-align:center;
  }
  .eb-success.is-visible{display:block;}
  .eb-form.is-hidden{display:none;}
  .eb-success h4{font-family:'Poppins',sans-serif;color:var(--eb-navy);font-size:17px;margin-bottom:6px;}
  .eb-success p{font-size:14px;color:var(--eb-muted);line-height:1.6;margin:0;}

  .eb-fine{max-width:680px;margin:36px auto 0;text-align:center;font-size:12.5px;line-height:1.6;color:var(--eb-muted);}
</style>
</head>
<body>

<section class="eb-giveaway">
  <div class="eb-wrap">

    <div class="eb-head">
      <span class="eb-eyebrow">🎁 Free Shirt Giveaway</span>
      <h2>Wear the mission.<br><span>Win the shirt.</span></h2>
      <p>Every entry helps spread the word about EmpowerBands' safety wristbands. One supporter wins a free EmpowerBands tee, on us — and everyone who enters helps a band reach one more community.</p>
    </div>

    <div class="eb-grid">

      <div class="eb-card eb-shirt-card">
        <span class="eb-shirt-badge">Free to win</span>
        <svg class="eb-shirt-svg" viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="EmpowerBands t-shirt">
          <path d="M62 30 L38 46 L28 74 L48 84 L56 68 L56 172 L144 172 L144 68 L152 84 L172 74 L162 46 L138 30 C138 30 128 42 100 42 C72 42 62 30 62 30 Z"
                fill="#EAF1FF" stroke="#2D6CDF" stroke-width="4" stroke-linejoin="round"/>
          <path d="M84 62 C88 76 112 76 116 62" stroke="#2D6CDF" stroke-width="3" fill="none" stroke-linecap="round"/>
          <text x="100" y="118" text-anchor="middle" font-family="Poppins, sans-serif" font-weight="800" font-size="15" fill="#1F4FB0">EMPOWER</text>
          <text x="100" y="136" text-anchor="middle" font-family="Poppins, sans-serif" font-weight="700" font-size="11" fill="#FF6B57" letter-spacing="2">BANDS</text>
        </svg>
        <h3>EmpowerBands Tee</h3>
        <p>Soft, everyday t-shirt featuring the EmpowerBands logo — wear the mission wherever you go.</p>
        <div class="eb-price-row">
          <span class="eb-price">$25</span>
          <span class="eb-price-note">if you'd rather not wait to win</span>
        </div>
        <a class="eb-buy-link" href="mailto:support@empowerbands.org?subject=Order:%20EmpowerBands%20T-Shirt">Buy one now &rarr;</a>
      </div>

      <div class="eb-card eb-entry-card">
        <h3>How to enter</h3>
        <ol class="eb-steps">
          <li>
            <span class="eb-step-num">1</span>
            <p>Follow the mission on <a href="https://linktr.ee/EmpowerBandsWorldwide" target="_blank" rel="noopener">our Linktree</a> — every platform is there.</p>
          </li>
          <li>
            <span class="eb-step-num">2</span>
            <p>Share the word — tag a friend or repost something about EmpowerBands.</p>
          </li>
          <li>
            <span class="eb-step-num">3</span>
            <p>Drop your name and email below to lock in your entry.</p>
          </li>
        </ol>

        <form class="eb-form" id="eb-giveaway-form">
          <div class="eb-field">
            <label for="eb-name">Name</label>
            <input type="text" id="eb-name" name="name" placeholder="Your name" required>
          </div>
          <div class="eb-field">
            <label for="eb-email">Email</label>
            <input type="email" id="eb-email" name="email" placeholder="name@email.com" required>
          </div>
          <div class="eb-field">
            <label for="eb-social">Social handle (optional)</label>
            <input type="text" id="eb-social" name="social" placeholder="@yourhandle">
          </div>
          <button type="submit" class="eb-submit">🎁 Enter to win</button>
          <p class="eb-form-note">No purchase necessary. One entry per person.</p>
        </form>

        <div class="eb-success" id="eb-success">
          <h4>You're entered 💙</h4>
          <p>We'll open your email app to confirm your entry with our team. Keep an eye on your inbox — winners are announced by email.</p>
        </div>
      </div>

    </div>

    <p class="eb-fine">Giveaway run by EmpowerBands Worldwide, Decatur, Alabama. No purchase necessary to enter or win. Winner selected at random and notified by email. Void where prohibited. Questions: <a href="mailto:support@empowerbands.org" style="color:var(--eb-blue-dark);">support@empowerbands.org</a>.</p>

  </div>
</section>

<script>
  (function(){
    var form = document.getElementById('eb-giveaway-form');
    var success = document.getElementById('eb-success');
    form.addEventListener('submit', function(e){
      e.preventDefault();
      var name = document.getElementById('eb-name').value.trim();
      var email = document.getElementById('eb-email').value.trim();
      var social = document.getElementById('eb-social').value.trim();

      var subject = encodeURIComponent('Giveaway Entry: EmpowerBands Tee');
      var body = encodeURIComponent(
        'Name: ' + name + '\n' +
        'Email: ' + email + '\n' +
        'Social handle: ' + (social || 'n/a') + '\n\n' +
        'Entering the free t-shirt giveaway.'
      );
      window.location.href = 'mailto:support@empowerbands.org?subject=' + subject + '&body=' + body;

      form.classList.add('is-hidden');
      success.classList.add('is-visible');
    });
  })();
</script>

</body>
</html>
