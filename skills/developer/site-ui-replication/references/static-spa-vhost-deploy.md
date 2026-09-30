# Deploying a static SPA build as its own nginx vhost

Proven on at-2 (`server.example.com`, Debian, nginx, acme.sh cert), 2026-09-22: a Vite
build published as port **3500**, additive alongside five other vhosts. The shape
generalises to any host that already runs nginx for several stacks.

**Why port-not-hostname:** adding a subdomain needs DNS *and* certificate work. A new
`listen <port> ssl http2` block reuses the existing cert and needs neither, so it is the
default for internal tools. Reach for a hostname only when someone outside the tailnet
needs it.

## 1. Recon the host before writing anything

```bash
ssh -i ~/.ssh/<key> -o BatchMode=yes user@<host> '
  sudo -n true && echo "sudo NOPASSWD ok"
  ss -ltn | grep -oE ":[0-9]+$" | tr -d : | sort -n | uniq   # which ports are taken
  ls /etc/nginx/sites-enabled/                                # the vhost idiom to copy
  sudo ls /etc/ssl/nginx/                                     # cert + key filenames
'
```

Then **read one existing vhost end to end** and copy its idiom — cert paths, the
`include ssl.conf`, the `server_name`, the proxy/serve style. Matching the neighbours
is what makes the addition boring.

## 2. The vhost

```nginx
server {
    listen 3500 ssl http2;
    listen [::]:3500 ssl http2;
    server_name server.example.com;
    ssl_certificate     /etc/ssl/nginx/server.example.com-cert.pem;
    ssl_certificate_key /etc/ssl/nginx/server.example.com-key.pem;
    include ssl.conf;

    root  /var/www/abc-ui;
    index index.html;

    # Without this, a hard refresh on /selleragent/properties 404s.
    location / {
        try_files $uri $uri/ /index.html;
    }
    # Vite/webpack emit content-hashed names, so these are immutable.
    location /assets/ {
        add_header Cache-Control "public, max-age=31536000, immutable";
        try_files $uri =404;
    }
    location = /index.html { add_header Cache-Control "no-cache"; }

    gzip on;
    gzip_types text/css application/javascript application/json image/svg+xml;
    gzip_min_length 1024;
}
```

Install additively, and **hash the neighbours first**:

```bash
sudo md5sum /etc/nginx/sites-enabled/*     # before
sudo cp abc-ui.conf /etc/nginx/sites-available/abc-ui
sudo ln -sf /etc/nginx/sites-available/abc-ui /etc/nginx/sites-enabled/abc-ui
sudo nginx -t && sudo systemctl reload nginx
sudo md5sum /etc/nginx/sites-enabled/*     # after: identical except yours
```

`nginx -t` before the reload is the cheap guard; re-hashing plus curling every other
port afterwards is what lets you state "nothing else moved" as fact.

## 3. Static files

```bash
tar czf /tmp/dist.tgz -C dist .
scp -i ~/.ssh/<key> /tmp/dist.tgz user@<host>:/tmp/dist.tgz
ssh ... 'sudo mkdir -p /var/www/abc-ui && sudo rm -rf /var/www/abc-ui/*
         sudo tar xzf /tmp/dist.tgz -C /var/www/abc-ui
         sudo chown -R www-data:www-data /var/www/abc-ui'
```

## 4. Prove the new build is live, not just that nginx reloaded

A content-hashed filename is the proof. Read it back from the server and compare with
what you just built:

```bash
ls dist/index.html                                   # local
curl -sk https://<host>:3500/ | grep -o 'index-[A-Za-z0-9_-]*\.js'   # served
```

Equal names = that exact artefact is being served. For a behavioural change, grep the
served bundle for a token unique to your edit as a second check, and for a *removal*
assert a count of 0 (`grep -c 'old-string'` → `0`), which proves the deletion shipped
rather than only the addition.

## 5. Verify every route, and the neighbours

```bash
for p in / /selleragent/overview /onboarding /login; do
  curl -sk -o /dev/null -w "%{http_code} %{content_type}\n" https://<host>:3500$p
done
# other stacks still up
for p in 3300 3400 9443 9444 9446; do
  curl -sk -o /dev/null -w "$p %{http_code}\n" https://127.0.0.1:$p/
done
```

A status code only proves **routing**. Confirm content in a real browser — and note
that a SPA fallback server returns 200 with an empty shell for *every* path, so a 200
is worth nothing about whether a route renders.

## Traps

- **`sudo docker ps` vs `ss`:** on a host where Docker needs sudo, a bare `ss -ltnp`
  shows `permission denied ... docker.sock` for container-owned ports. Read the LISTEN
  ports, not the process owners, or run docker under sudo.
- **A shared host's container count is not a failure signal.** Other people deploy
  there. Attribute an unfamiliar container before reacting:
  `docker inspect <name> --format '{{index .Config.Labels "com.docker.compose.project.config_files"}} | {{.State.StartedAt}}'`.
- **Do not edit an existing vhost for a new service.** Copy it, change the port and
  root, and add a new symlink. Editing the shared file risks the other product that
  also uses it.
- **Ports already in use on the server (survey first):** 3300, 3400, 9443-9446
  on one project. Port 3500 was free.

## Keeping it repeatable

Commit both scripts into the app repo so the next deploy is one command, and have the
deploy script run the verification suites as its last step:

```
First time:   ./install-vhost.sh   # scp vhost, symlink, nginx -t, reload
Every deploy: ./deploy-at2.sh      # build -> copy -> reload -> verify (both suites)
```

Put the vhost under `nginx/<name>.conf` in the repo — then the host's config is
reproducible from source instead of living only on the box.
