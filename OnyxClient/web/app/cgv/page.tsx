import type { Metadata } from 'next'
import { LegalPage, type LegalSection } from '@/components/legal-page'
import { PRODUCTS, formatPrice } from '@/lib/products'

export const metadata: Metadata = {
  title: 'Conditions Générales de Vente — Onyx Client',
  description: "Conditions Générales de Vente des licences Onyx Client.",
}

const priceList = PRODUCTS.map((p) => `${p.name} : ${formatPrice(p.priceInCents)}`).join(' ; ')

const sections: LegalSection[] = [
  {
    title: 'Objet',
    paragraphs: [
      "Les présentes Conditions Générales de Vente (CGV) régissent la vente de licences d'utilisation du logiciel Onyx Client (ci-après « le Logiciel ») sur le site Onyx Client (ci-après « le Site »).",
      "Toute commande implique l'acceptation pleine et entière des présentes CGV ainsi que des Conditions Générales d'Utilisation (CGU).",
    ],
  },
  {
    title: 'Vendeur',
    paragraphs: [
      "Le Site est édité par [Nom / raison sociale à compléter], [statut juridique, ex. micro-entreprise], immatriculé sous le numéro SIRET [à compléter], dont le siège est situé [adresse à compléter].",
      'Contact : [adresse e-mail de contact à compléter].',
    ],
  },
  {
    title: 'Produits',
    paragraphs: [
      "Le Site propose des licences numériques donnant accès au Logiciel, un programme Windows (.exe) d'automatisation de mouvements pour le jeu Rocket League (macros, wavedash, etc.).",
      "Chaque licence correspond à une clé unique. Les durées proposées sont : 1 semaine, 1 mois ou « à vie ». La licence « à vie » est valable pour toute la durée d'exploitation du Logiciel par le Vendeur.",
      "Une clé est liée au premier ordinateur sur lequel elle est activée et ne peut pas être utilisée simultanément sur plusieurs machines.",
    ],
  },
  {
    title: 'Prix',
    paragraphs: [
      `Les prix sont indiqués en euros, toutes taxes comprises : ${priceList}.`,
      "Le Vendeur se réserve le droit de modifier ses prix à tout moment. Les licences sont facturées au prix en vigueur au moment de la validation de la commande.",
    ],
  },
  {
    title: 'Commande',
    paragraphs: [
      "Pour commander, l'utilisateur doit créer un compte sur le Site, ajouter une ou plusieurs licences à son panier, puis procéder au paiement.",
      "La commande est définitive après confirmation du paiement. Un récapitulatif de la commande et les clés achetées sont alors affichés et restent consultables dans l'espace « Mon compte ».",
    ],
  },
  {
    title: 'Paiement',
    paragraphs: [
      "Le paiement s'effectue en ligne par carte bancaire via le prestataire sécurisé Stripe. Le Vendeur n'a jamais accès aux coordonnées bancaires de l'acheteur.",
      "En cas de refus de paiement, la commande est annulée et aucune clé n'est délivrée.",
    ],
  },
  {
    title: 'Livraison',
    paragraphs: [
      "La livraison est immédiate et dématérialisée : les clés sont générées automatiquement dès la confirmation du paiement et affichées à l'écran ainsi que dans l'espace « Mon compte ». Le Logiciel est téléchargeable depuis ce même espace.",
    ],
  },
  {
    title: 'Droit de rétractation',
    paragraphs: [
      "Conformément à l'article L221-28 13° du Code de la consommation, le droit de rétractation ne peut être exercé pour la fourniture d'un contenu numérique non fourni sur un support matériel dont l'exécution a commencé avec l'accord préalable exprès du consommateur et son renoncement exprès à son droit de rétractation.",
      "En validant sa commande, l'acheteur demande expressément la fourniture immédiate de sa clé et reconnaît perdre son droit de rétractation dès sa délivrance.",
    ],
  },
  {
    title: 'Remboursement',
    paragraphs: [
      "Aucun remboursement n'est accordé après délivrance d'une clé, sauf si le Logiciel est inutilisable du fait d'un défaut imputable au Vendeur et que celui-ci n'a pas pu le corriger dans un délai raisonnable après signalement.",
      "Une clé révoquée pour non-respect des CGU (partage, revente, tentative de contournement) ne donne lieu à aucun remboursement.",
    ],
  },
  {
    title: 'Responsabilité',
    paragraphs: [
      "L'utilisation de logiciels tiers ou de macros peut être contraire aux conditions d'utilisation de Rocket League, de Psyonix ou d'Epic Games et entraîner des sanctions sur le compte de jeu (avertissement, suspension, bannissement). L'acheteur utilise le Logiciel sous sa seule responsabilité.",
      "Le Vendeur ne saurait être tenu responsable d'une sanction appliquée au compte de jeu de l'acheteur, ni d'une incompatibilité due à une mise à jour du jeu.",
    ],
  },
  {
    title: 'Données personnelles',
    paragraphs: [
      "Les données collectées (adresse e-mail, historique de commandes, identifiant matériel lié à la clé) sont utilisées uniquement pour la gestion des comptes, des commandes et des licences. Elles ne sont jamais revendues.",
      "Conformément au RGPD, l'acheteur dispose d'un droit d'accès, de rectification et de suppression de ses données en écrivant à l'adresse de contact indiquée à l'article 2.",
    ],
  },
  {
    title: 'Droit applicable et litiges',
    paragraphs: [
      "Les présentes CGV sont soumises au droit français. En cas de litige, une solution amiable sera recherchée avant toute action judiciaire.",
      "Le consommateur peut recourir gratuitement à un médiateur de la consommation [nom et coordonnées du médiateur à compléter], ou à la plateforme européenne de règlement en ligne des litiges.",
    ],
  },
]

export default function CgvPage() {
  return (
    <LegalPage
      eyebrow="Légal"
      title="Conditions Générales de Vente"
      updatedAt="11 avril 2026"
      intro="Ces conditions s'appliquent à tout achat de licence Onyx Client effectué sur ce site."
      sections={sections}
      otherDoc={{ href: '/cgu', label: "Conditions Générales d'Utilisation" }}
    />
  )
}
